Parallel execution allows multiple branches of your graph to run concurrently, improving performance and enabling complex workflows where independent tasks can be processed simultaneously.

## Overview

GraphAI supports parallel execution in two main scenarios:

1. **Graph-level parallelism**: When a node has multiple outgoing edges, all successor nodes execute concurrently
2. **Router-level parallelism**: When a router returns multiple choices, all selected branches execute concurrently

## Parallel Branches with Edges

When you add multiple edges from a single source node to different destination nodes, those destinations will execute in parallel.

### Basic Example

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

# Create parallel branches from start
g.add_edge(start, branch_a)
g.add_edge(start, branch_b)

# Both branches lead to end
g.add_edge(branch_a, end)
g.add_edge(branch_b, end)

result = await g.execute(input={"input": {}})
# result contains: {"a": 1, "b": 2}
```

In this example, `branch_a` and `branch_b` execute concurrently after `start` completes. Their outputs are merged into the final state.

### Using `add_parallel()`

For convenience, you can use the `add_parallel()` method to create multiple edges at once:

```python
g = Graph()
g.add_node(start).add_node(branch_a).add_node(branch_b).add_node(end)

# Equivalent to adding edges individually
g.add_parallel(start, [branch_a, branch_b])

g.add_edge(branch_a, end)
g.add_edge(branch_b, end)
```

## Joining Parallel Branches

By default, when parallel branches converge to a common node, that node executes once for each incoming branch. To ensure the convergence node executes only once after all branches complete, use `add_join()`.

### Without Join (Multiple Executions)

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
# state["history"] contains TWO "end" entries because end runs for each branch
```

### With Join (Single Execution)

```python
g = Graph()
g.add_node(start).add_node(branch_a).add_node(branch_b).add_node(end)
g.add_edge(start, branch_a)
g.add_edge(start, branch_b)

# Use add_join to synchronize branches
g.add_join([branch_a, branch_b], end)

await g.execute(input={"input": {}})
state = g.get_state()
# state["history"] contains only ONE "end" entry
```

The `add_join()` method ensures that:
- All specified branches must complete before the destination node executes
- The destination node executes exactly once
- State from all branches is merged before continuing

## Nested Parallel Execution

You can create parallel branches at multiple levels in your graph:

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

# Linear edge to mid
g.add_edge(start, mid)

# Mid forks to two parallel branches
g.add_edge(mid, branch_a)
g.add_edge(mid, branch_b)

# Both branches converge at end
g.add_join([branch_a, branch_b], end)

result = await g.execute(input={"input": {}})
# result contains: {"mid": True, "a": 1, "b": 2}
```

## Router Parallel Execution

Routers can also trigger parallel execution by returning multiple choices instead of a single choice.

### Single Choice (Standard Behavior)

The standard router behavior selects one branch:

```python
from graphai import router

@router
async def single_router(input: dict):
    return {"choice": "tool_a"}  # Only tool_a executes
```

### Multiple Choices (Parallel Execution)

Return `choices` (a list) instead of `choice` to execute multiple branches concurrently:

```python
@router
async def parallel_router(input: dict):
    return {"choices": ["tool_a", "tool_b"]}  # Both execute in parallel
```

### Full Example

```python
from graphai import Graph, node, router

@node(start=True)
async def start(input: dict):
    return {}

@router
async def parallel_router(input: dict):
    # Return multiple choices for parallel execution
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
g.add_edge(parallel_router, tool_c)  # tool_c has an edge but is not in choices
g.add_join([tool_a, tool_b], end)

result = await g.execute({"input": {}})

# Results from parallel branches are merged into state
assert result["a_result"] == 1
assert result["b_result"] == 2
# tool_c is NOT executed because it's not in the choices array
assert "c_result" not in result
```

> **Note**: When a parallel router shares an edge with a node that is not included in the router's `choices` array, that node will not be executed. Only nodes whose names appear in the returned `choices` list will run. In the example above, `tool_c` has an edge from the router but is not included in `choices`, so it does not execute.

### Router with Join (Iterative Patterns)

Use `add_join()` to control where execution continues after parallel branches complete. This enables iterative workflows where a router can evaluate results and decide whether to run more parallel branches:

```python
@node(start=True)
async def start(input: dict):
    return {}

@router(name="parallel_router")
async def parallel_router(input: dict, state: dict):
    iteration = state.get("iteration", 0)

    if iteration > 0:
        # After first iteration, proceed to end
        return {"choice": "end"}

    state["iteration"] = iteration + 1
    # Run tools in parallel, then return to this router via join
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
g.add_join([tool_a, tool_b], parallel_router)  # Return to router after parallel execution
g.add_edge(parallel_router, end)

result = await g.execute({"input": {}})
# Router is called twice: first returns choices, second returns choice to end
```

The join pattern with routers is useful for:
- Iterative workflows that may need multiple rounds of parallel execution
- Gathering results from parallel branches before deciding next steps
- Implementing tool-calling agents that can invoke multiple tools simultaneously

## State Merging

When parallel branches complete, their outputs are merged into the state:

1. **Output merging**: Each branch's return values are merged into the final state
2. **Conflict resolution**: If branches return the same key, the last branch to complete wins

```python
result = await g.execute({"input": {}})

# Results from all branches merged into state
result["a_result"]  # From tool_a
result["b_result"]  # From tool_b
```

## Best Practices

1. **Use `add_join()` for convergence**: When multiple branches should synchronize before continuing, always use `add_join()` to prevent duplicate execution of downstream nodes.

2. **Keep parallel branches independent**: Parallel branches execute concurrently with copied state. Avoid relying on one branch's state changes being visible to another.

3. **Use `add_join()` for iterative patterns**: When a router needs to make decisions after parallel execution, use `add_join()` to route back to the router node. This keeps flow control in the graph structure rather than in node return values.

4. **Name nodes explicitly for routers**: When using router parallel execution, ensure destination nodes have explicit names that match the choices returned by the router.

## Next Steps

- Learn about [Graphs](graphs.md) for general graph construction
- Explore [State](state.md) management for understanding how state flows through parallel branches
- Check out [Callbacks](callbacks.md) for monitoring parallel execution progress
