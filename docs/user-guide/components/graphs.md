The `Graph` is what ties everything together. It holds your nodes and routers, connects them with edges, and runs them in order.

## The pieces

- **Nodes** do the work.
- **Edges** say which node runs next.
- **State** is the shared dict that carries data through the run.

## Creating a graph

```python
from graphai import Graph

graph = Graph()

# or with a step limit and some starting state
graph = Graph(max_steps=20, initial_state={"history": []})
```

- `max_steps` (default `10`) caps how many steps a run can take, so a loop can't run forever. Hitting the cap raises `MaxStepsError`.
- `initial_state` seeds the state dict.

## Adding nodes

Add each node you've defined. Constructor methods return the graph, so you can chain them.

```python
graph.add_node(my_node)

graph.add_node(node_a).add_node(node_b).add_node(node_c)
```

A node is one of:

- **Start node** — the entry point. Exactly one per graph.
- **End node** — an exit point. As many as you need.
- **Regular node** — a processing step.
- **Router** — a node that decides where to go next.

## Connecting nodes

Edges define the flow. You can pass node objects or their names:

```python
graph.add_edge(source_node, destination_node)
graph.add_edge("node_a", "node_b")
```

A straight-line workflow is just a chain of edges:

```python
graph.add_edge(node_a, node_b)
graph.add_edge(node_b, node_c)
```

Give one node several outgoing edges and the successors run concurrently — see [Parallel Execution](parallel-execution.md). For side work that shouldn't affect the main path, use [Branches](branches.md).

## Routers

A router picks the next node at run time. Register it with the nodes that lead into it and the nodes it can send to:

```python
graph.add_router(
    sources=[node_a],
    router=my_router,
    destinations=[node_b, node_c],
)
```

The router returns a `"choice"` naming the next node:

```python
@router
async def my_router(input: dict):
    if some_condition:
        return {"choice": "node_b", "data": processed_data}
    return {"choice": "node_c", "data": processed_data}
```

Return `"choices"` (a list) instead to run several destinations in parallel.

## Running the graph

```python
import asyncio

async def run_graph():
    result = await graph.execute(input={"input": {"query": "Hello, world!"}})
    return result

result = asyncio.run(run_graph())
```

Here's the one thing to really understand: **the dict you pass to `execute()` becomes the state**, and each node receives only the parameters it declares, looked up by name from that state. A node with an `input` parameter gets `state["input"]`. That's why the request goes under an `input` key above. `execute()` returns the final state.

### What happens during a run

1. Execution starts at the start node.
2. Each node gets its declared parameters from the state, runs, and returns a dict.
3. That dict is merged into the state.
4. At a router, the `"choice"` decides the next node.
5. It continues until an end node runs — or `max_steps` is hit.

### Many inputs at once

`execute_many` runs the graph over several inputs concurrently:

```python
results = await graph.execute_many(
    [{"input": {"query": "one"}}, {"input": {"query": "two"}}],
    concurrency=5,
)
```

Results come back in input order.

## State

The graph keeps a state dict for the whole run:

```python
state = graph.get_state()
graph.set_state({"history": [], "context": "some context"})   # replace
graph.update_state({"new_key": "new_value"})                   # merge
graph.reset_state()                                             # clear
```

A node can read the state by declaring a `state` parameter. Changes persist either way — mutate it in place, or return the keys you want merged:

```python
@node
async def my_node(input: dict, state: dict):
    history = state.get("history", [])
    return {"output": result, "history": history + [result]}
```

[State](state.md) goes into more detail.

## Validating the graph

`compile()` checks the graph before you run it, and raises `GraphCompileError` if something's wrong:

```python
graph.compile()

# also reject cycles
graph.compile(strict=True)
```

It checks for a start node, at least one end node, and that every node is reachable. Cycles — like a router that loops back to itself through a tool — are allowed by default, because they're how agents iterate. Pass `strict=True` to forbid them.

## Visualizing

```python
graph.visualize()
```

Draws the graph, with branch edges dashed. You'll need `networkx` or `matplotlib` installed.

## Next steps

- [Nodes](nodes.md) — building processing steps
- [Parallel Execution](parallel-execution.md) — forks and joins
- [Branches](branches.md) — side pipelines off the main path
- [State](state.md) — carrying context through a run
- [Callbacks](callbacks.md) — streaming
