# Branches

A **branch** is a side pipeline that starts when a node finishes, without
becoming part of the main path. Use it for work that should happen *because*
a node ran (log a result, notify a system, write a row) but that must never
change where the main path goes next.

## Why not a second edge?

Two regular edges out of one node mean "fork and join": every successor runs
concurrently and the graph expects them to meet again at a join. That is the
right shape for parallel work, but not for a side effect. If the main path is
a router loop (`router -> tool -> router`) and you hang a second regular edge
off the tool, the fork changes how the loop terminates. A branch edge does not
take part in the fork/join mechanism at all.

## Adding a branch

```python
from graphai import Graph, node

@node
async def send_email(input: dict):
    ...
    return {"input": input, "success": True, "node_output": {"to": "a@b.c"}}

@node
async def log_email(input: dict, upstream: dict | None = None):
    # upstream == {"node": "send_email", "output": {...send_email's output...}}
    return {"input": input}

graph.add_branch(send_email, log_email)
```

`add_branch(source, destination, *, condition=None, wait=True)`:

- **`destination`** is the first node of the branch. The branch then follows
  the regular edges leaving it, one node after another, and stops at the first
  node with no successors. It needs no end node and no join. A node whose
  output contains `success: False` also stops the branch, so a failed step does
  not feed the steps after it.
- **`condition`** is an optional callable `(output, state) -> bool` (it may be
  `async`). It receives the source node's output dict and the graph state; the
  branch is skipped when it returns a falsy value.
- **`wait`** decides whether the main path pauses until the branch finishes
  (`True`, the default) or continues immediately (`False`). Detached branches
  are still awaited by `execute()` before it returns, so nothing is left
  running when a run is reported complete.

Branches may hang off any node, including routers, and a node inside a branch
may have branches of its own.

## Errors

An exception inside a branch never propagates to the main path. It is logged
and recorded on the graph:

```python
result = await graph.execute(input={"input": {}})
for err in graph.branch_errors:
    print(err.source, "->", err.destination, err.error)
```

`branch_errors` is reset at the start of every `execute()`.

## The `upstream` parameter

Every node invocation now carries an `upstream` entry in its local state:
`{"node": <name of the node that ran before>, "output": <its output dict>}`.
A node can read it by declaring the parameter:

```python
@node
async def shape(input: dict, upstream: dict | None = None):
    rows = (upstream or {}).get("output", {}).get("node_output")
    ...
```

Nodes that do not declare `upstream` are unaffected, and it is removed from
the dict `execute()` returns.
