Branches let a node start a side pipeline when it finishes, without changing where the main path goes next. Use them for work that should happen *because* a node ran, such as logging a result or writing rows to a table.

## Adding a Branch

Create a branch with `add_branch()`. The destination runs after the source completes; the main path continues along its regular edges as if the branch were not there:

```python
from graphai import Graph, node

@node(start=True)
async def start(input: dict):
    return {}

@node
async def main(input: dict):
    return {"main": True}

@node
async def side(input: dict):
    return {"side": True}

@node(end=True)
async def end(input: dict):
    return {}

g = Graph()
g.add_node(start).add_node(main).add_node(side).add_node(end)

g.add_edge(start, main)
g.add_edge(main, end)
g.add_branch(main, side)   # side runs after main, off the main path

result = await g.execute(input={"input": {}})
# result contains: {"main": True}
# "side" is not in result: a branch never writes into the main path
```

A branch needs no join and no end node. It stops at the first node with no outgoing edges.

## Multi-Step Branches

The branch target can lead to further nodes through ordinary edges. Together they form a pipeline that runs to its last step:

```python
g.add_branch(main, shape)      # pipeline starts here
g.add_edge(shape, validate)    # ordinary edges between steps
g.add_edge(validate, write)    # write has no successors, so the pipeline ends there
```

If a step returns `{"success": False}`, the steps after it do not run.

## Reading the Previous Node

Every node can declare an `upstream` parameter. It holds the name and output of the node that ran just before it, so a pipeline step can read what it was given:

```python
@node
async def shape(input: dict, upstream: dict | None = None):
    rows = upstream["output"]["rows"]   # the previous node returned {"rows": [...]}
    return {"rows": [r | {"source": "api"} for r in rows]}
```

`upstream` is available on the main path too, and nodes that do not declare it are unaffected.

## Conditions

Pass a `condition` to decide at run time whether the branch runs. It receives the source node's output and the graph state and may be sync or async:

```python
def only_on_success(output: dict, state: dict) -> bool:
    return output.get("success") is True

g.add_branch(main, side, condition=only_on_success)
```

## Detached Branches

By default the main path waits for a branch to finish before moving on. Pass `wait=False` to let it continue immediately:

```python
g.add_branch(main, side, wait=False)
```

`execute()` still waits for every detached branch before it returns, so nothing is left running when a run is reported complete.

## Errors

An exception inside a branch never reaches the main path. It is logged and recorded on the graph:

```python
await g.execute(input={"input": {}})

for err in g.branch_errors:
    print(err.source, "->", err.destination, err.error)
```

`branch_errors` is cleared at the start of each `execute()`.

## Branches on Routers and Loops

A branch can hang off any node, including a node inside a router loop. The loop is unaffected because a branch is not one of the node's successors:

```python
g.add_edge(brain, tool)
g.add_edge(tool, brain)      # the loop
g.add_branch(tool, log)      # log runs each time tool runs
```

## Next Steps

- Compare branches with forks in [Parallel Execution vs Branching](parallel-vs-branching.md)
- Learn how forks and joins work in [Parallel Execution](parallel-execution.md)
- See how outputs flow between nodes in [State](state.md)
