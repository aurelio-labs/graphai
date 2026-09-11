Parallel execution lets independent parts of your graph run at the same time. When several tools can work on a request at once, there's no reason to wait for them one by one.

GraphAI runs things in parallel in two situations:

1. **Forks** — a node has several outgoing edges, so all of its successors run concurrently.
2. **Router fan-out** — a router returns several `choices`, so all of them run concurrently.

## Forking with edges

Give one node more than one outgoing edge and the destinations run in parallel.

```python
from graphai import Graph, node

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

# fork from start
g.add_edge(start, branch_a)
g.add_edge(start, branch_b)

# both lead to end
g.add_edge(branch_a, end)
g.add_edge(branch_b, end)

result = await g.execute(input={"input": {}})
# result contains: {"a": 1, "b": 2}
```

`branch_a` and `branch_b` run concurrently once `start` finishes, and their outputs are merged into the state.

`add_parallel()` is shorthand for the same fork:

```python
g.add_parallel(start, [branch_a, branch_b])

g.add_edge(branch_a, end)
g.add_edge(branch_b, end)
```

## Joining the branches

Here's the catch. When parallel branches converge on the same node, that node runs **once per incoming branch** by default. Usually you want it to run once, after everything has finished. That's what `add_join()` is for.

Without a join, `end` runs twice:

```python
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
g.add_edge(start, branch_a)
g.add_edge(start, branch_b)
g.add_edge(branch_a, end)
g.add_edge(branch_b, end)

await g.execute(input={"input": {}})
state = g.get_state()
# state["history"] has TWO "end" entries
```

With a join, it runs once:

```python
g = Graph()
g.add_node(start).add_node(branch_a).add_node(branch_b).add_node(end)
g.add_edge(start, branch_a)
g.add_edge(start, branch_b)

g.add_join([branch_a, branch_b], end)

await g.execute(input={"input": {}})
state = g.get_state()
# state["history"] has ONE "end" entry
```

`add_join()` guarantees that every listed branch finishes first, the destination runs exactly once, and the branches' state is merged before it continues.

## Nesting forks

Forks can happen at any depth:

```python
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

g.add_edge(start, mid)          # linear
g.add_edge(mid, branch_a)       # then mid forks
g.add_edge(mid, branch_b)
g.add_join([branch_a, branch_b], end)

result = await g.execute(input={"input": {}})
# result contains: {"mid": True, "a": 1, "b": 2}
```

## Router fan-out

A router normally picks one path:

```python
from graphai import router

@router
async def single_router(input: dict):
    return {"choice": "tool_a"}  # only tool_a runs
```

Return `choices` (a list) instead and every listed node runs in parallel:

```python
@router
async def parallel_router(input: dict):
    return {"choices": ["tool_a", "tool_b"]}  # both run
```

A full example:

```python
from graphai import Graph, node, router

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

@node(name="tool_c")
async def tool_c(input: dict):
    return {"c_result": 3}

@node(end=True)
async def end(input: dict):
    return {}

g = Graph()
g.add_node(start).add_node(parallel_router).add_node(tool_a).add_node(tool_b).add_node(tool_c).add_node(end)
g.add_edge(start, parallel_router)
g.add_edge(parallel_router, tool_a)
g.add_edge(parallel_router, tool_b)
g.add_edge(parallel_router, tool_c)  # has an edge, but isn't in choices
g.add_join([tool_a, tool_b], end)

result = await g.execute({"input": {}})

assert result["a_result"] == 1
assert result["b_result"] == 2
assert "c_result" not in result  # tool_c never ran
```

Only nodes named in `choices` run. `tool_c` has an edge from the router, but the router didn't choose it, so it's skipped.

### Looping back through a join

Join the parallel branches back into the router and you get an iterative loop — run tools, look at the results, decide whether to go again:

```python
@node(start=True)
async def start(input: dict):
    return {}

@router(name="parallel_router")
async def parallel_router(input: dict, state: dict):
    iteration = state.get("iteration", 0)

    if iteration > 0:
        return {"choice": "end"}       # second time through: finish

    state["iteration"] = iteration + 1
    return {"choices": ["tool_a", "tool_b"]}

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
g.add_join([tool_a, tool_b], parallel_router)  # back to the router
g.add_edge(parallel_router, end)

result = await g.execute({"input": {}})
# the router runs twice: first it fans out, then it chooses end
```

This is the shape of a tool-calling agent that can fire several tools at once, gather the results, and decide what to do next. Keep an eye on `max_steps` — each parallel layer counts as one step, and the loop is bounded by it.

## How state merges

When parallel branches finish, their outputs are merged into the state. If two branches return the same key, the last one to finish wins.

```python
result = await g.execute({"input": {}})

result["a_result"]  # from tool_a
result["b_result"]  # from tool_b
```

## Good habits

1. **Join where branches converge.** Otherwise downstream nodes run once per branch.
2. **Keep branches independent.** They run concurrently on copied state — don't assume one can see another's changes.
3. **Loop through a join, not through return values.** Routing back to the router with `add_join()` keeps the control flow in the graph structure.
4. **Name router destinations explicitly.** The names in `choices` must match the nodes.

## Next steps

- [Graphs](graphs.md) — general graph construction
- [State](state.md) — how state flows through parallel branches
- [Callbacks](callbacks.md) — watching parallel progress
- [Parallel Execution vs Branching](parallel-vs-branching.md) — forks vs. side pipelines
