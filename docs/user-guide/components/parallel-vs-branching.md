GraphAI has two ways for one node to lead to more than one node. A **fork** (two or more regular edges) runs successors concurrently as part of the main path. A **branch** runs a side pipeline that stays out of the main path. They look similar on a diagram and behave very differently.

## The Same Nodes, Two Wirings

```python
from graphai import Graph, node

@node(start=True)
async def start(input: dict):
    return {}

@node
async def a(input: dict):
    return {"a": 1}

@node
async def b(input: dict):
    return {"b": 2}

@node(end=True)
async def end(input: dict):
    return {}
```

### As a fork

```python
g = Graph()
g.add_node(start).add_node(a).add_node(b).add_node(end)

g.add_edge(start, a)
g.add_edge(start, b)               # second edge out of start: a fork
g.add_join([a, b], end)            # forks converge with a join

result = await g.execute(input={"input": {}})
# result contains: {"a": 1, "b": 2}
```

### As a branch

```python
g = Graph()
g.add_node(start).add_node(a).add_node(b).add_node(end)

g.add_edge(start, a)
g.add_edge(a, end)                 # the main path
g.add_branch(start, b)             # b is a side pipeline off start

result = await g.execute(input={"input": {}})
# result contains: {"a": 1}
```

## What Differs

| | Fork | Branch |
|---|---|---|
| Created with | two or more `add_edge()` calls | `add_branch()` |
| Runs | all successors concurrently | the branch after the source completes |
| Must end | at a join or an end node | wherever the pipeline runs out of edges |
| Result | outputs of every path merged | main path only |
| On error | the first exception aborts `execute()` | recorded in `branch_errors`, run continues |
| Waiting | until every path finishes | until the branch finishes, or not at all with `wait=False` |
| Conditional | no | optional `condition` callable |

## Choosing

Use a **fork** when the paths are parts of one result and the graph needs all of them before it can continue, such as running several tools at once and then deciding what to do with the combined output.

Use a **branch** when the work is a consequence of a node running and the main path should not depend on it, such as writing a log row, notifying another system, or syncing data after a tool call.

## Inside a Router Loop

The difference matters most in a loop. Here a router repeatedly calls a tool and the tool returns to the router:

```python
g.add_edge(brain, tool)
g.add_edge(tool, brain)
```

Adding a fork off the tool changes how the loop terminates, because the router path is now one arm of a fork that expects to join. Adding a branch does not:

```python
g.add_branch(tool, log)   # log runs after each tool call; the loop is unchanged
```

## Mixing Them

A branch's pipeline may itself fork and join, and a node inside a pipeline may have branches of its own:

```python
g.add_branch(main, shape)
g.add_edge(shape, write)
g.add_edge(shape, notify)          # a fork inside the pipeline
g.add_join([write, notify], done)
```

## Next Steps

- Full details in [Branches](branches.md)
- Forks, joins and router choices in [Parallel Execution](parallel-execution.md)
