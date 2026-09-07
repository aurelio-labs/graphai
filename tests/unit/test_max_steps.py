import pytest

from graphai import Graph, MaxStepsError, node, router


def _build_router_loop(max_steps: int, stop_after: int) -> tuple[Graph, dict]:
    """start -> llm(router) -> tool -> llm -> ... until the router picks end."""
    calls = {"router": 0, "tool": 0}

    @node(start=True)
    async def start(input: dict):
        """Start node"""
        return {"x": 0}

    @router
    async def llm(x: int):
        """Router that keeps calling the tool until stop_after"""
        calls["router"] += 1
        if calls["router"] > stop_after:
            return {"choice": "end", "x": x}
        return {"choice": "tool", "x": x}

    @node
    async def tool(x: int):
        """Tool node"""
        calls["tool"] += 1
        return {"x": x + 1}

    @node(end=True)
    async def end(x: int):
        """End node"""
        return {"x": x}

    graph = Graph(max_steps=max_steps)
    for n in (start, llm, tool, end):
        graph.add_node(n)
    graph.add_edge(start, llm)
    # add_router wires tool -> llm itself
    graph.add_router(sources=[tool], router=llm, destinations=[tool, end])
    graph.compile()
    return graph, calls


class TestMaxSteps:
    @pytest.mark.asyncio
    async def test_router_loop_raises_max_steps(self):
        # router never chooses end within the budget
        graph, calls = _build_router_loop(max_steps=5, stop_after=1000)
        with pytest.raises(MaxStepsError) as exc:
            await graph.execute({"input": {}})
        assert exc.value.max_steps == 5
        # start + 4 router/tool nodes were invoked, the 6th node never ran
        assert calls["router"] + calls["tool"] == 4

    @pytest.mark.asyncio
    async def test_router_loop_within_budget_completes(self):
        # start, llm, tool, llm, tool, llm(end choice), end -> 7 node invocations
        graph, calls = _build_router_loop(max_steps=7, stop_after=2)
        result = await graph.execute({"input": {}})
        assert result["x"] == 2
        assert calls == {"router": 3, "tool": 2}

    @pytest.mark.asyncio
    async def test_sequential_chain_raises_max_steps(self):
        @node(start=True)
        async def a(input: str):
            """A"""
            return {"input": input}

        @node
        async def b(input: str):
            """B"""
            return {"input": input}

        @node
        async def c(input: str):
            """C"""
            return {"input": input}

        @node(end=True)
        async def d(input: str):
            """D"""
            return {"input": input}

        graph = Graph(max_steps=2)
        for n in (a, b, c, d):
            graph.add_node(n)
        graph.add_edge(a, b)
        graph.add_edge(b, c)
        graph.add_edge(c, d)
        graph.compile()
        with pytest.raises(MaxStepsError):
            await graph.execute({"input": "x"})
