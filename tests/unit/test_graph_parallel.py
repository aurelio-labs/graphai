import pytest
from graphai import node, router, Graph


@pytest.mark.asyncio
async def test_parallel_branches_merge_state():
    """Two successors from a single node should run concurrently and merge results."""

    @node(start=True)
    async def start(input: dict):
        return {}

    @node
    async def branch_a(input: dict):
        return {"a": 1}

    @node
    async def branch_b(input: dict):
        return {"b": 2}

    @node(end=True)
    async def end(input: dict):
        return {}

    g = Graph()
    # add nodes
    g.add_node(start).add_node(branch_a).add_node(branch_b).add_node(end)
    # define edges so start branches to A and B in parallel
    g.add_edge(start, branch_a)
    g.add_edge(start, branch_b)
    # both branches lead to a common end
    g.add_edge(branch_a, end)
    g.add_edge(branch_b, end)

    result = await g.execute(input={"input": {}})
    # both branch outputs should be present in the final state
    assert result.get("a") == 1
    assert result.get("b") == 2


@pytest.mark.asyncio
async def test_parallel_nested_branches():
    """Nested parallel execution (branching at multiple levels) should merge all results."""

    @node(start=True)
    async def start(input: dict):
        return {}

    @node
    async def mid(input: dict):
        return {"mid": True}

    @node
    async def branch_a(input: dict):
        return {"a": 1}

    @node
    async def branch_b(input: dict):
        return {"b": 2}

    @node(end=True)
    async def end(input: dict):
        return {}

    g = Graph()
    g.add_node(start).add_node(mid).add_node(branch_a).add_node(branch_b).add_node(end)
    # linear edge to mid
    g.add_edge(start, mid)
    # mid forks to two branches
    g.add_edge(mid, branch_a)
    g.add_edge(mid, branch_b)
    # both branches go to end
    g.add_edge(branch_a, end)
    g.add_edge(branch_b, end)

    result = await g.execute(input={"input": {}})
    assert result["mid"] is True
    assert result["a"] == 1
    assert result["b"] == 2


@pytest.mark.asyncio
async def test_add_parallel():
    """The add_parallel convenience method should wire up multiple edges for concurrent execution."""

    @node(start=True)
    async def start(input: dict):
        return {}

    @node
    async def branch_a(input: dict):
        return {"a": 1}

    @node
    async def branch_b(input: dict):
        return {"b": 2}

    @node(end=True)
    async def end(input: dict):
        return {}

    g = Graph()
    g.add_node(start).add_node(branch_a).add_node(branch_b).add_node(end)
    # use the new helper to branch in parallel
    g.add_parallel(start, [branch_a, branch_b])
    g.add_edge(branch_a, end)
    g.add_edge(branch_b, end)

    result = await g.execute(input={"input": {}})
    assert result["a"] == 1
    assert result["b"] == 2


@pytest.mark.asyncio
async def test_router_node_not_parallel():
    """A router node should still choose one successor, not branch in parallel."""

    @node(start=True)
    async def start(input: dict):
        return {}

    @router
    async def chooser(input: dict):
        # always choose branch_a
        return {"choice": "branch_a"}

    @node(name="branch_a")
    async def branch_a(input: dict):
        return {"a": 1}

    @node(name="branch_b")
    async def branch_b(input: dict):
        return {"b": 2}

    @node(end=True)
    async def end(input: dict):
        return {}

    g = Graph()
    g.add_node(start).add_node(chooser).add_node(branch_a).add_node(branch_b).add_node(
        end
    )
    # linear to router
    g.add_edge(start, chooser)
    # router can go to either branch, but chooser selects 'branch_a'
    g.add_edge(chooser, branch_a)
    g.add_edge(chooser, branch_b)
    # both branches connect to end
    g.add_edge(branch_a, end)
    g.add_edge(branch_b, end)

    result = await g.execute(input={"input": {}})
    # only branch_a should run; branch_b's output should not appear
    assert result.get("a") == 1
    assert "b" not in result
