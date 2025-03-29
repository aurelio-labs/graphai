import inspect
from typing import Any, Callable, Dict, Optional
from pydantic import Field

from graphai.callback import Callback
from graphai.utils import FunctionSchema


class NodeMeta(type):
    @staticmethod
    def positional_to_kwargs(cls_type, args) -> Dict[str, Any]:
        init_signature = inspect.signature(cls_type.__init__)
        init_params = {
            name: arg
            for name, arg in init_signature.parameters.items()
            if name != "self"
        }
        return init_params

    def __call__(cls, *args, **kwargs):
        named_positional_args = NodeMeta.positional_to_kwargs(cls, args)
        kwargs.update(named_positional_args)
        return super().__call__(**kwargs)


class _Node:
    def __init__(
        self,
        is_router: bool = False,
    ):
        self.is_router = is_router

    def _node(
        self,
        func: Callable,
        start: bool = False,
        end: bool = False,
        stream: bool = False,
        name: str | None = None,
    ) -> Callable:
        """Decorator validating node structure."""
        if not callable(func):
            raise ValueError("Node must be a callable function.")

        func_signature = inspect.signature(func)
        schema: FunctionSchema = FunctionSchema.from_callable(func)

        class NodeClass:
            _func_signature = func_signature
            is_router: bool = Field(
                default=False, description="Whether the node is a router."
            )
            # following attributes will be overridden by the decorator
            name: str | None = Field(default=None, description="The name of the node.")
            is_start: bool = Field(
                default=False, description="Whether the node is the start of the graph."
            )
            is_end: bool = Field(
                default=False, description="Whether the node is the end of the graph."
            )
            schema: FunctionSchema | None = Field(
                default=None, description="The schema of the node."
            )
            stream: bool = Field(
                default=False, description="Whether the node includes streaming object."
            )

            def __init__(self):
                self._expected_params = set(self._func_signature.parameters.keys())

            async def execute(self, *args, **kwargs):
                # Prepare arguments, including callback if stream is True
                params_dict = await self._parse_params(*args, **kwargs)
                return await func(**params_dict)  # Pass only the necessary arguments

            async def _parse_params(self, *args, **kwargs) -> Dict[str, Any]:
                # filter out unexpected keyword args
                expected_kwargs = {
                    k: v for k, v in kwargs.items() if k in self._expected_params
                }
                # Convert args to kwargs based on the function signature
                args_names = list(self._func_signature.parameters.keys())[
                    1 : len(args) + 1
                ]  # skip 'self'
                expected_args_kwargs = dict(zip(args_names, args))
                # Combine filtered args and kwargs
                combined_params = {**expected_args_kwargs, **expected_kwargs}

                # Bind the current instance attributes to the function signature
                if "callback" in self._expected_params and not stream:
                    raise ValueError(
                        f"Node {func.__name__}: requires stream=True when callback is defined."
                    )
                bound_params = self._func_signature.bind_partial(**combined_params)
                # get the default parameters (if any)
                bound_params.apply_defaults()
                params_dict = bound_params.arguments.copy()
                # Filter arguments to match the next node's parameters
                filtered_params = {
                    k: v for k, v in params_dict.items() if k in self._expected_params
                }
                # confirm all required parameters are present
                missing_params = [
                    p for p in self._expected_params if p not in filtered_params
                ]
                # if anything is missing we raise an error
                if missing_params:
                    raise ValueError(
                        f"Missing required parameters for the {func.__name__} node: {', '.join(missing_params)}"
                    )
                return filtered_params

            @classmethod
            def get_signature(cls):
                """Returns the signature of the decorated function as LLM readable
                string.
                """
                signature_components = []
                if NodeClass._func_signature:
                    for param in NodeClass._func_signature.parameters.values():
                        if param.default is param.empty:
                            signature_components.append(
                                f"{param.name}: {param.annotation}"
                            )
                        else:
                            signature_components.append(
                                f"{param.name}: {param.annotation} = {param.default}"
                            )
                else:
                    return "No signature"
                return "\n".join(signature_components)

            @classmethod
            async def invoke(
                cls,
                input: Dict[str, Any],
                callback: Optional[Callback] = None,
                state: Optional[Dict[str, Any]] = None,
            ):
                if callback:
                    if stream:
                        input["callback"] = callback
                    else:
                        raise ValueError(
                            f"Error in node {func.__name__}. When callback provided, stream must be True."
                        )
                # Add state to the input if present and the parameter exists in the function signature
                if state is not None and "state" in cls._func_signature.parameters:
                    input["state"] = state

                instance = cls()
                out = await instance.execute(**input)
                return out

        NodeClass.__name__ = func.__name__
        node_class_name = name or func.__name__
        if node_class_name is None:
            raise ValueError("Unexpected error: node name not set.")
        NodeClass.name = node_class_name
        NodeClass.__doc__ = func.__doc__
        NodeClass.is_start = start
        NodeClass.is_end = end
        NodeClass.is_router = self.is_router
        NodeClass.stream = stream
        NodeClass.schema = schema
        return NodeClass

    def __call__(
        self,
        func: Optional[Callable] = None,
        start: bool = False,
        end: bool = False,
        stream: bool = False,
        name: str | None = None,
    ):
        # We must wrap the call to the decorator in a function for it to work
        # correctly with or without parenthesis
        def wrap(
            func: Callable, start=start, end=end, stream=stream, name=name
        ) -> Callable:
            return self._node(func=func, start=start, end=end, stream=stream, name=name)

        if func:
            # Decorator is called without parenthesis
            return wrap(func=func, start=start, end=end, stream=stream, name=name)
        # Decorator is called with parenthesis
        return wrap


node = _Node()
router = _Node(is_router=True)
