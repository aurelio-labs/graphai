import asyncio
from pydantic import Field
from typing import Optional, Any
from collections.abc import AsyncIterator


log_stream = True


class Callback:
    identifier: str = Field(
        default="graphai",
        description=(
            "The identifier for special tokens. This allows us to easily "
            "identify special tokens in the stream so we can handle them "
            "correctly in any downstream process."
        ),
    )
    special_token_format: str = Field(
        default="<{identifier}:{token}:{params}>",
        description=(
            "The format for special tokens. This is used to format special "
            "tokens so they can be easily identified in the stream. "
            "The format is a string with three possible components:\n"
            "- {identifier}: An identifier shared by all special tokens, "
            "by default this is 'graphai'.\n"
            "- {token}: The special token type to be streamed. This may "
            "be a tool name, identifier for start/end nodes, etc.\n"
            "- {params}: Any additional parameters to be streamed. The parameters "
            "are formatted as a comma-separated list of key-value pairs."
        ),
        examples=[
            "<{identifier}:{token}:{params}>",
            "<[{identifier} | {token} | {params}]>",
            "<{token}:{params}>",
        ],
    )
    token_format: str = Field(
        default="{token}",
        description=(
            "The format for streamed tokens. This is used to format the "
            "tokens typically returned from LLMs. By default, no special "
            "formatting is applied."
        ),
    )
    _first_token: bool = Field(
        default=True,
        description="Whether this is the first token in the stream.",
        exclude=True,
    )
    _current_node_name: Optional[str] = Field(
        default=None, description="The name of the current node.", exclude=True
    )
    _active: bool = Field(
        default=True, description="Whether the callback is active.", exclude=True
    )
    _done: bool = Field(
        default=False,
        description="Whether the stream is done and should be closed.",
        exclude=True,
    )
    queue: asyncio.Queue

    def __init__(
        self,
        identifier: str = "graphai",
        special_token_format: str = "<{identifier}:{token}:{params}>",
        token_format: str = "{token}",
    ):
        self.identifier = identifier
        self.special_token_format = special_token_format
        self.token_format = token_format
        self.queue = asyncio.Queue()
        self._done = False
        self._first_token = True
        self._current_node_name = None
        self._active = True

    @property
    def first_token(self) -> bool:
        return self._first_token

    @first_token.setter
    def first_token(self, value: bool):
        self._first_token = value

    @property
    def current_node_name(self) -> Optional[str]:
        return self._current_node_name

    @current_node_name.setter
    def current_node_name(self, value: Optional[str]):
        self._current_node_name = value

    @property
    def active(self) -> bool:
        return self._active

    @active.setter
    def active(self, value: bool):
        self._active = value

    def __call__(self, token: str, node_name: Optional[str] = None):
        if self._done:
            raise RuntimeError("Cannot add tokens to a closed stream")
        self._check_node_name(node_name=node_name)
        # otherwise we just assume node is correct and send token
        self.queue.put_nowait(token)

    async def acall(self, token: str, node_name: Optional[str] = None):
        # TODO JB: do we need to have `node_name` param?
        if self._done:
            raise RuntimeError("Cannot add tokens to a closed stream")
        self._check_node_name(node_name=node_name)
        # otherwise we just assume node is correct and send token
        self.queue.put_nowait(token)

    async def aiter(self) -> AsyncIterator[str]:
        """Used by receiver to get the tokens from the stream queue. Creates
        a generator that yields tokens from the queue until the END token is
        received.
        """
        end_token = await self._build_special_token(name="END", params=None)
        while True:  # Keep going until we see the END token
            try:
                if self._done and self.queue.empty():
                    break
                token = await self.queue.get()
                yield token
                self.queue.task_done()
                if token == end_token:
                    break
            except asyncio.CancelledError:
                break
        self._done = True  # Mark as done after processing all tokens

    async def start_node(self, node_name: str, active: bool = True):
        """Starts a new node and emits the start token."""
        if self._done:
            raise RuntimeError("Cannot start node on a closed stream")
        self.current_node_name = node_name
        if self.first_token:
            self.first_token = False
        self.active = active
        if self.active:
            token = await self._build_special_token(
                name=f"{self.current_node_name}:start", params=None
            )
            self.queue.put_nowait(token)
            # TODO JB: should we use two tokens here?
            node_token = await self._build_special_token(
                name=self.current_node_name, params=None
            )
            self.queue.put_nowait(node_token)

    async def end_node(self, node_name: str):
        """Emits the end token for the current node."""
        if self._done:
            raise RuntimeError("Cannot end node on a closed stream")
        # self.current_node_name = node_name
        if self.active:
            node_token = await self._build_special_token(
                name=f"{self.current_node_name}:end", params=None
            )
            self.queue.put_nowait(node_token)

    async def close(self):
        """Close the stream and prevent further tokens from being added.
        This will send an END token and set the done flag to True.
        """
        if self._done:
            return
        end_token = await self._build_special_token(name="END", params=None)
        self._done = True  # Set done before putting the end token
        self.queue.put_nowait(end_token)
        # Don't wait for queue.join() as it can cause deadlock
        # The stream will close when aiter processes the END token

    def _check_node_name(self, node_name: Optional[str] = None):
        if node_name:
            # we confirm this is the current node
            if self.current_node_name != node_name:
                raise ValueError(
                    f"Node name mismatch: {self.current_node_name} != {node_name}"
                )

    async def _build_special_token(
        self, name: str, params: dict[str, Any] | None = None
    ):
        if params:
            params_str = ",".join([f"{k}={v}" for k, v in params.items()])
        else:
            params_str = ""
        if self.identifier:
            identifier = self.identifier
        else:
            identifier = ""
        return self.special_token_format.format(
            identifier=identifier, token=name, params=params_str
        )
