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

@pytest.mark.asyncio
async def test_parallel_state_brances():
    """Parallel execution without join edge will result in multiple end outputs."""

    @node(start=True)
    async def start(input: dict, state: dict):
        state["history"] = ["start"]
        return {}

    @node
    async def branch_a(input: dict, state: dict):
        state["history"].append("branch_a")
        return {}

    @node
    async def branch_b(input: dict, state: dict):
        state["history"].append("branch_b")
        return {}

    @node(end=True)
    async def end(input: dict, state: dict):
        state["history"].append("end")
        return {}

    g = Graph()
    g.add_node(start).add_node(branch_a).add_node(branch_b).add_node(end)
    # linear to router
    g.add_edge(start, branch_a)
    g.add_edge(start, branch_b)
    # both branches connect to end
    g.add_edge(branch_a, end)
    g.add_edge(branch_b, end)

    _ = await g.execute(input={"input": {}})
    # assert that the state contains everything from both branches
    state = g.get_state()
    assert "start" in state["history"] 
    assert "branch_a" in state["history"] 
    assert "branch_b" in state["history"] 
    assert "end" in state["history"] 
    # assert that we have two "end" in state history
    assert len([x for x in state["history"] if x == "end"]) == 2


@pytest.mark.asyncio
async def test_parallel_state_join():
    """Parallel execution with join edge will result in one end output."""

    @node(start=True)
    async def start(input: dict, state: dict):
        state["history"] = ["start"]
        return {}

    @node
    async def branch_a(input: dict, state: dict):
        state["history"].append("branch_a")
        return {}

    @node
    async def branch_b(input: dict, state: dict):
        state["history"].append("branch_b")
        return {}

    @node(end=True)
    async def end(input: dict, state: dict):
        state["history"].append("end")
        return {}

    g = Graph()
    g.add_node(start).add_node(branch_a).add_node(branch_b).add_node(end)
    # linear to router
    g.add_edge(start, branch_a)
    g.add_edge(start, branch_b)
    # both branches connect to end via join
    g.add_join([branch_a, branch_b], end)

    _ = await g.execute(input={"input": {}})
    # assert that the state contains everything from both branches
    state = g.get_state()
    assert "start" in state["history"]
    assert "branch_a" in state["history"]
    assert "branch_b" in state["history"]
    assert "end" in state["history"]
    # assert that we only have one "end" in state history
    assert len([x for x in state["history"] if x == "end"]) == 1


@pytest.mark.asyncio
async def test_router_parallel_choices():
    """Router returning multiple choices should execute all in parallel."""

    @node(start=True)
    async def start(input: dict):
        return {}

    @router
    async def parallel_router(input: dict):
        return {"choices": ["tool_a", "tool_b"]}

    @node(name="tool_a")
    async def tool_a(input: dict):
        return {"a_result": 1}

    @node(name="tool_b")
    async def tool_b(input: dict):
        return {"b_result": 2}

    @node(end=True)
    async def end(input: dict):
        return {}

    g = Graph()
    g.add_node(start).add_node(parallel_router).add_node(tool_a).add_node(tool_b).add_node(end)
    g.add_edge(start, parallel_router)
    g.add_edge(parallel_router, tool_a)
    g.add_edge(parallel_router, tool_b)
    g.add_edge(tool_a, end)
    g.add_edge(tool_b, end)

    result = await g.execute({"input": {}})

    assert "parallel_results" in result
    assert "tool_a" in result["parallel_results"]
    assert "tool_b" in result["parallel_results"]
    assert result["a_result"] == 1
    assert result["b_result"] == 2


@pytest.mark.asyncio
async def test_router_parallel_with_continuation():
    """Router with continuation should return to specified node after parallel execution."""

    call_count = {"router": 0}

    @node(start=True)
    async def start(input: dict):
        return {}

    @router(name="parallel_router")
    async def parallel_router(input: dict):
        call_count["router"] += 1
        if call_count["router"] > 1:
            return {"choice": "end"}
        return {
            "choices": ["tool_a", "tool_b"],
            "continuation": "parallel_router",
        }

    @node(name="tool_a")
    async def tool_a(input: dict):
        return {"a_result": 1}

    @node(name="tool_b")
    async def tool_b(input: dict):
        return {"b_result": 2}

    @node(end=True)
    async def end(input: dict):
        return {"final": "done"}

    g = Graph()
    g.add_node(start).add_node(parallel_router).add_node(tool_a).add_node(tool_b).add_node(end)
    g.add_edge(start, parallel_router)
    g.add_edge(parallel_router, tool_a)
    g.add_edge(parallel_router, tool_b)
    g.add_edge(parallel_router, end)
    g.add_edge(tool_a, end)
    g.add_edge(tool_b, end)

    result = await g.execute({"input": {}})

    assert call_count["router"] == 2
    assert "parallel_results" in result
    assert result["final"] == "done"


@pytest.mark.asyncio
async def test_router_single_choice_still_works():
    """Existing single-choice router behavior should be unchanged."""

    @node(start=True)
    async def start(input: dict):
        return {}

    @router
    async def single_router(input: dict):
        return {"choice": "tool_a"}

    @node(name="tool_a")
    async def tool_a(input: dict):
        return {"a_result": 1}

    @node(name="tool_b")
    async def tool_b(input: dict):
        return {"b_result": 2}

    @node(end=True)
    async def end(input: dict):
        return {}

    g = Graph()
    g.add_node(start).add_node(single_router).add_node(tool_a).add_node(tool_b).add_node(end)
    g.add_edge(start, single_router)
    g.add_edge(single_router, tool_a)
    g.add_edge(single_router, tool_b)
    g.add_edge(tool_a, end)
    g.add_edge(tool_b, end)

    result = await g.execute({"input": {}})

    assert result["a_result"] == 1
    assert "b_result" not in result
    assert "parallel_results" not in result
