import pytest
import asyncio
from graphai.callback import Callback
from graphai import node, Graph


@pytest.fixture
async def callback():
    cb = Callback()
    yield cb
    await cb.close()


@pytest.fixture
async def define_graph():
    """Define a graph with nodes that stream and don't stream."""

    @node(start=True)
    async def node_start(input: str):
        # no stream added here
        return {"input": input}

    @node(stream=True)
    async def node_a(input: str, callback: Callback):
        tokens = ["Hello", "World", "!"]
        for token in tokens:
            await callback.acall(token)
        return {"input": input}

    @node(stream=True)
    async def node_b(input: str, callback: Callback):
        tokens = ["Here", "is", "node", "B", "!"]
        for token in tokens:
            await callback.acall(token)
        return {"input": input}

    @node
    async def node_c(input: str):
        # no stream added here
        return {"input": input}

    @node(stream=True)
    async def node_d(input: str, callback: Callback):
        tokens = ["Here", "is", "node", "D", "!"]
        for token in tokens:
            await callback.acall(token)
        return {"input": input}

    @node(end=True)
    async def node_end(input: str):
        return {"input": input}

    graph = Graph()

    nodes = [node_start, node_a, node_b, node_c, node_d, node_end]

    for i, node_fn in enumerate(nodes):
        graph.add_node(node_fn)
        if i > 0:
            graph.add_edge(nodes[i - 1], node_fn)

    graph.compile()

    return graph


async def stream(cb: Callback, text: str):
    tokens = text.split(" ")
    for token in tokens:
        await cb.acall(token)
    await cb.close()
    return


class TestCallbackConfig:
    @pytest.mark.asyncio
    async def test_callback_initialization(self):
        """Test basic initialization of Callback class"""
        cb = Callback()
        assert cb.identifier == "graphai"
        assert cb.special_token_format == "<{identifier}:{token}:{params}>"
        assert cb.token_format == "{token}"
        assert isinstance(cb.queue, asyncio.Queue)

    @pytest.mark.asyncio
    async def test_custom_initialization(self):
        """Test initialization with custom parameters"""
        cb = Callback(
            identifier="custom",
            special_token_format="[{identifier}:{token}:{params}]",
            token_format="<<{token}>>",
        )
        assert cb.identifier == "custom"
        assert cb.special_token_format == "[{identifier}:{token}:{params}]"
        assert cb.token_format == "<<{token}>>"
        # create streaming task
        asyncio.create_task(stream(cb, "Hello"))
        out_tokens = []
        # now stream
        async for token in cb.aiter():
            out_tokens.append(token)
        assert out_tokens == ["Hello", "[custom:END:]"]

    @pytest.mark.asyncio
    async def test_default_tokens(self):
        """Test default tokens"""
        cb = Callback()
        # create streaming task
        asyncio.create_task(stream(cb, "Hello"))
        out_tokens = []
        # now stream
        async for token in cb.aiter():
            out_tokens.append(token)
        assert out_tokens == ["Hello", "<graphai:END:>"]

    @pytest.mark.asyncio
    async def test_custom_tokens(self):
        """Test custom tokens"""
        cb = Callback(
            identifier="custom",
            special_token_format="[{identifier}:{token}:{params}]",
            token_format="<<{token}>>",
        )
        # create streaming task
        asyncio.create_task(stream(cb, "Hello"))
        out_tokens = []
        # now stream
        async for token in cb.aiter():
            out_tokens.append(token)
        assert out_tokens == ["Hello", "[custom:END:]"]


class TestCallbackGraph:
    @pytest.mark.asyncio
    async def test_callback_graph(self, define_graph):
        """Test callback graph"""
        graph = await define_graph
        cb = graph.get_callback()
        asyncio.create_task(graph.execute(input={"input": "Hello"}))
        out_tokens = []
        async for token in cb.aiter():
            out_tokens.append(token)
        assert out_tokens == [
            "<graphai:node_a:start:>",
            "<graphai:node_a:>",
            "Hello",
            "World",
            "!",
            "<graphai:node_a:end:>",
            "<graphai:node_b:start:>",
            "<graphai:node_b:>",
            "Here",
            "is",
            "node",
            "B",
            "!",
            "<graphai:node_b:end:>",
            "<graphai:node_d:start:>",
            "<graphai:node_d:>",
            "Here",
            "is",
            "node",
            "D",
            "!",
            "<graphai:node_d:end:>",
            "<graphai:END:>",
        ]

    @pytest.mark.asyncio
    async def test_custom_callback_graph(self, define_graph):
        """Test callback graph"""
        graph = await define_graph
        cb = graph.get_callback()
        cb.identifier = "custom"
        cb.special_token_format = "[{identifier}:{token}:{params}]"
        cb.token_format = "<<{token}>>"
        asyncio.create_task(graph.execute(input={"input": "Hello"}))
        out_tokens = []
        async for token in cb.aiter():
            out_tokens.append(token)
        assert out_tokens == [
            "[custom:node_a:start:]",
            "[custom:node_a:]",
            "Hello",
            "World",
            "!",
            "[custom:node_a:end:]",
            "[custom:node_b:start:]",
            "[custom:node_b:]",
            "Here",
            "is",
            "node",
            "B",
            "!",
            "[custom:node_b:end:]",
            "[custom:node_d:start:]",
            "[custom:node_d:]",
            "Here",
            "is",
            "node",
            "D",
            "!",
            "[custom:node_d:end:]",
            "[custom:END:]",
        ]


# @pytest.mark.asyncio
# async def test_start_node(callback):
#     """Test starting a node"""
#     await callback.start_node("test_node")
#     token = callback.queue.get_nowait()
#     assert token == "<graphai:start:test_node>"

# @pytest.mark.asyncio
# async def test_end_node(callback):
#     """Test ending a node"""
#     await callback.start_node("test_node")
#     await callback.end_node("test_node")
#     # Get and discard the start token
#     _ = callback.queue.get_nowait()
#     token = callback.queue.get_nowait()
#     assert token == "<graphai:end:test_node>"

# @pytest.mark.asyncio
# async def test_node_name_mismatch(callback):
#     """Test node name mismatch error"""
#     await callback.start_node("node1")
#     with pytest.raises(ValueError, match="Node name mismatch"):
#         callback("test token", node_name="node2")

# @pytest.mark.asyncio
# async def test_token_streaming(callback):
#     """Test basic token streaming"""
#     await callback.start_node("test_node")
#     test_tokens = ["Hello", " ", "World", "!"]

#     for token in test_tokens:
#         await callback.acall(token, node_name="test_node")

#     # Skip the start node token
#     _ = callback.queue.get_nowait()

#     # Check each streamed token
#     for expected_token in test_tokens:
#         token = callback.queue.get_nowait()
#         assert token == expected_token

# @pytest.mark.asyncio
# async def test_aiter_streaming(callback):
#     """Test async iteration over tokens"""
#     test_tokens = ["Hello", " ", "World", "!"]

#     await callback.start_node("test_node")
#     for token in test_tokens:
#         await callback.acall(token, node_name="test_node")
#     await callback.end_node("test_node")
#     await callback.close()

#     received_tokens = []
#     async for token in callback.aiter():
#         received_tokens.append(token)

#     assert len(received_tokens) == len(test_tokens) + 3  # +3 for start, end, and END tokens
#     assert received_tokens[0] == "<graphai:start:test_node>"
#     assert received_tokens[-2] == "<graphai:end:test_node>"
#     assert received_tokens[-1] == "<graphai:END>"
#     assert received_tokens[1:-2] == test_tokens

# @pytest.mark.asyncio
# async def test_inactive_node(callback):
#     """Test behavior when node is inactive"""
#     await callback.start_node("test_node", active=False)
#     await callback.acall("This shouldn't be queued", node_name="test_node")
#     await callback.end_node("test_node")

#     with pytest.raises(asyncio.QueueEmpty):
#         callback.queue.get_nowait()

# @pytest.mark.asyncio
# async def test_build_special_token(callback):
#     """Test building special tokens with parameters"""
#     token = await callback._build_special_token(
#         "test",
#         params={"key": "value", "number": 42}
#     )
#     assert token == "<graphai:test:key=value,number=42>"

#     # Test with no params
#     token = await callback._build_special_token("test")
#     assert token == "<graphai:test:>"

# @pytest.mark.asyncio
# async def test_close(callback):
#     """Test closing the callback"""
#     await callback.close()
#     token = callback.queue.get_nowait()
#     assert token == "<graphai:END>"

# @pytest.mark.asyncio
# async def test_sequential_nodes(callback):
#     """Test handling multiple sequential nodes"""
#     # First node
#     await callback.start_node("node1")
#     await callback.acall("token1", node_name="node1")
#     await callback.end_node("node1")

#     # Second node
#     await callback.start_node("node2")
#     await callback.acall("token2", node_name="node2")
#     await callback.end_node("node2")

#     expected_sequence = [
#         "<graphai:start:node1>",
#         "token1",
#         "<graphai:end:node1>",
#         "<graphai:start:node2>",
#         "token2",
#         "<graphai:end:node2>"
#     ]

#     for expected in expected_sequence:
#         token = callback.queue.get_nowait()
#         assert token == expected
