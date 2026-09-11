Nodes are the units of work in GraphAI. Each one is an async function that takes some input and returns a dict. You connect them into a graph.

## Defining a node

Decorate an async function with `@node`:

```python
from graphai import node

@node
async def process_data(input: dict):
    result = do_something(input["data"])
    return {"output": result}
```

Every node must be `async`, and must return a dict.

## How a node gets its arguments

This is the most important thing to understand about nodes, so it's worth spelling out.

The graph keeps a state dict. When a node runs, GraphAI looks at the node's signature and passes **only the parameters it declares, pulled from the state by name**. Nothing else.

So this node receives `state["input"]`:

```python
@node
async def my_node(input: dict):
    ...
```

And this one receives `state["query"]` and `state["metadata"]`, ignoring everything else in the state:

```python
@node
async def selective(query: str, metadata: dict = None):
    return {"result": process(query, metadata)}
```

A parameter with no default is required. If it isn't in the state, the run fails with a clear error.

## What a node returns

The dict a node returns is merged into the state, where later nodes can read it:

```python
@node
async def my_node(input: dict):
    result = process(input["data"])
    return {
        "processed_data": result,
        "metadata": {"timestamp": time.time()},
    }
```

## Kinds of node

### Start and end

One start node marks the entry point. Any number of end nodes mark exits.

```python
@node(start=True)
async def entry(input: dict):
    return {"initialized_data": input}

@node(end=True)
async def exit(input: dict):
    return {"final_result": processed_result}
```

### Streaming

Set `stream=True` and declare a `callback` parameter to stream tokens out while the node runs:

```python
@node(stream=True)
async def streaming_node(input: dict, callback):
    for chunk in process_chunks(input["data"]):
        await callback.acall(chunk)
    return {"result": "streaming complete"}
```

[Callbacks](callbacks.md) covers this in depth.

### Routers

A router decides which node runs next. It returns a `"choice"` with the next node's name:

```python
from graphai import router

@router
async def route_on_content(input: dict):
    if "question" in input["query"].lower():
        return {"choice": "question_node", "query": input["query"]}
    return {"choice": "statement_node", "statement": input["query"]}
```

Return `"choices"` (a list of names) to run several nodes in parallel instead. Routers are often driven by an LLM — the [quickstart](../../get-started/quickstart.md) builds one that picks between tools.

## Reading state and the previous node

Declare a `state` parameter to read the shared state. You can change it in place, or return keys to merge — both persist:

```python
@node
async def stateful(input: dict, state: dict):
    history = state.get("history", [])
    result = process_with_history(input["data"], history)
    return {"result": result, "history": history + [result]}
```

Declare `upstream` to see the node that ran just before this one — its name and its output:

```python
@node
async def shape(input: dict, upstream: dict | None = None):
    rows = upstream["output"]["rows"]
    return {"rows": rows}
```

## Naming nodes

A node's name defaults to the function name. Set it explicitly when a router needs to refer to it:

```python
@node(name="data_processor")
async def process_data(input: dict):
    return {"processed": result}
```

## Next steps

- [Graphs](graphs.md) — connecting nodes
- [State](state.md) — carrying context through a run
- [Callbacks](callbacks.md) — streaming responses
