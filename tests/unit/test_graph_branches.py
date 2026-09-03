import asyncio

import pytest

from graphai import Graph, node, router


def _linear_nodes():
    @node(start=True)
    async def start(input: dict):
        return {"input": input}

    @node
    async def work(input: dict):
        return {"input": input, "success": True, "node_output": {"rows": [1, 2]}}

    @node(end=True)
    async def end(input: dict):
        return {"input": input, "finished": True}

    return start, work, end


@pytest.mark.asyncio
async def test_branch_runs_after_source_and_main_path_still_reaches_end():
    start, work, end = _linear_nodes()
    seen: list[dict] = []

    @node
    async def side(input: dict, upstream: dict | None = None):
        seen.append(upstream or {})
        return {"input": input, "side": True}

    g = Graph()
    g.add_node(start).add_node(work).add_node(end).add_node(side)
    g.add_edge(start, work).add_edge(work, end)
    g.add_branch(work, side)

    result = await g.execute(input={"input": {}})

    assert result["finished"] is True
    assert len(seen) == 1
    assert seen[0]["node"] == "work"
    assert seen[0]["output"]["node_output"] == {"rows": [1, 2]}
    # branch output never leaks into the main path
    assert "side" not in result
    assert g.branch_errors == []


@pytest.mark.asyncio
async def test_branch_pipeline_follows_regular_edges_to_a_terminal():
    start, work, end = _linear_nodes()
    order: list[str] = []

    @node
    async def step_one(input: dict):
        order.append("one")
        return {"input": input, "success": True}

    @node
    async def step_two(input: dict, upstream: dict | None = None):
        order.append("two")
        assert upstream is not None and upstream["node"] == "step_one"
        return {"input": input, "success": True}

    g = Graph()
    for n in (start, work, end, step_one, step_two):
        g.add_node(n)
    g.add_edge(start, work).add_edge(work, end)
    g.add_edge(step_one, step_two)  # pipeline edge, step_two is a terminal
    g.add_branch(work, step_one)

    await g.execute(input={"input": {}})
    assert order == ["one", "two"]
    assert g.branch_errors == []


@pytest.mark.asyncio
async def test_branch_condition_sync_and_async():
    start, work, end = _linear_nodes()
    calls: list[str] = []

    @node
    async def skipped(input: dict):
        calls.append("skipped")
        return {"input": input}

    @node
    async def taken(input: dict):
        calls.append("taken")
        return {"input": input}

    async def async_true(output: dict, state: dict) -> bool:
        return output["node_output"]["rows"] == [1, 2]

    g = Graph()
    for n in (start, work, end, skipped, taken):
        g.add_node(n)
    g.add_edge(start, work).add_edge(work, end)
    g.add_branch(work, skipped, condition=lambda output, state: False)
    g.add_branch(work, taken, condition=async_true)

    await g.execute(input={"input": {}})
    assert calls == ["taken"]


@pytest.mark.asyncio
async def test_branch_failure_is_recorded_not_raised():
    start, work, end = _linear_nodes()

    @node
    async def explode(input: dict):
        raise RuntimeError("boom")

    g = Graph()
    for n in (start, work, end, explode):
        g.add_node(n)
    g.add_edge(start, work).add_edge(work, end)
    g.add_branch(work, explode)

    result = await g.execute(input={"input": {}})
    assert result["finished"] is True
    assert len(g.branch_errors) == 1
    err = g.branch_errors[0]
    assert (err.source, err.destination) == ("work", "explode")
    assert isinstance(err.error, RuntimeError)


@pytest.mark.asyncio
async def test_detached_branch_is_awaited_before_execute_returns():
    start, work, end = _linear_nodes()
    done = asyncio.Event()

    @node
    async def slow(input: dict):
        await asyncio.sleep(0.05)
        done.set()
        return {"input": input}

    g = Graph()
    for n in (start, work, end, slow):
        g.add_node(n)
    g.add_edge(start, work).add_edge(work, end)
    g.add_branch(work, slow, wait=False)

    await g.execute(input={"input": {}})
    assert done.is_set()
    assert not g._detached_tasks


@pytest.mark.asyncio
async def test_branch_from_tool_inside_router_loop_keeps_the_loop_alive():
    """The case a plain fork breaks: router -> tool -> router -> end, with a
    side pipeline hanging off the tool."""
    turns = {"n": 0}
    logged: list[str] = []

    @node(start=True)
    async def start(input: dict):
        return {"input": input}

    @router
    async def brain(input: dict):
        turns["n"] += 1
        return {"input": input, "choice": "tool" if turns["n"] == 1 else "end"}

    @node
    async def tool(input: dict):
        return {"input": input, "success": True, "node_output": {"sent": True}}

    @node
    async def log(input: dict, upstream: dict | None = None):
        logged.append((upstream or {}).get("node", ""))
        return {"input": input}

    @node(end=True)
    async def end(input: dict):
        return {"input": input, "finished": True}

    g = Graph()
    for n in (start, brain, tool, log, end):
        g.add_node(n)
    g.add_edge(start, brain).add_edge(brain, tool).add_edge(brain, end).add_edge(
        tool, brain
    )
    g.add_branch(tool, log)

    result = await g.execute(input={"input": {}})
    assert result.get("finished") is True
    assert turns["n"] == 2
    assert logged == ["tool"]


@pytest.mark.asyncio
async def test_pipeline_stops_after_a_failed_step():
    start, work, end = _linear_nodes()
    calls: list[str] = []

    @node
    async def failing(input: dict):
        calls.append("failing")
        return {"input": input, "success": False}

    @node
    async def never(input: dict):
        calls.append("never")
        return {"input": input}

    g = Graph()
    for n in (start, work, end, failing, never):
        g.add_node(n)
    g.add_edge(start, work).add_edge(work, end).add_edge(failing, never)
    g.add_branch(work, failing)

    await g.execute(input={"input": {}})
    assert calls == ["failing"]


@pytest.mark.asyncio
async def test_pipeline_fans_out_and_branches_can_nest():
    start, work, end = _linear_nodes()
    calls: list[str] = []

    @node
    async def first(input: dict):
        calls.append("first")
        return {"input": input}

    @node
    async def left(input: dict):
        calls.append("left")
        return {"input": input}

    @node
    async def right(input: dict):
        calls.append("right")
        return {"input": input}

    @node
    async def nested(input: dict):
        calls.append("nested")
        return {"input": input}

    g = Graph()
    for n in (start, work, end, first, left, right, nested):
        g.add_node(n)
    g.add_edge(start, work).add_edge(work, end)
    g.add_edge(first, left).add_edge(first, right)
    g.add_branch(work, first)
    g.add_branch(left, nested)

    await g.execute(input={"input": {}})
    assert calls[0] == "first"
    assert sorted(calls[1:]) == ["left", "nested", "right"]


def test_compile_reaches_branch_only_nodes():
    start, work, end = _linear_nodes()

    @node
    async def side(input: dict):
        return {"input": input}

    g = Graph()
    for n in (start, work, end, side):
        g.add_node(n)
    g.add_edge(start, work).add_edge(work, end)
    g.add_branch(work, side)
    # side is reachable only through the branch edge; compile must accept it
    g.compile(strict=True)


@pytest.mark.asyncio
async def test_main_path_upstream_is_previous_node():
    start, work, end = _linear_nodes()
    seen: list[str] = []

    @node
    async def probe(input: dict, upstream: dict | None = None):
        seen.append((upstream or {}).get("node", ""))
        return {"input": input}

    g = Graph()
    for n in (start, probe, work, end):
        g.add_node(n)
    g.add_edge(start, probe).add_edge(probe, work).add_edge(work, end)
    await g.execute(input={"input": {}})
    assert seen == ["start"]
