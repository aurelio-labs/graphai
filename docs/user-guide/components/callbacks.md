Callbacks are how a graph streams while it runs. A node can push tokens out as it produces them — an LLM's partial response, progress updates — and something outside the graph can consume them live. That's what makes streaming chat UIs and real-time endpoints possible.

## Use `EventCallback`

`EventCallback` emits structured `GraphEvent` objects instead of formatted strings, which makes the stream much easier to consume.

> `Callback`, the original string-based class, is deprecated and will be removed in v0.1.0. It still works, but new code should use `EventCallback`.

A `Graph` still creates the deprecated `Callback` by default, so tell it to use `EventCallback`:

```python
from graphai import Graph
from graphai.callback import EventCallback

graph = Graph()
graph.set_callback(EventCallback)
```

From then on, `graph.get_callback()` returns an `EventCallback`, and it's the default whenever `execute()` runs without one.

## Streaming from a node

Mark a node with `stream=True` and give it a `callback` parameter. GraphAI injects the callback for you.

```python
from graphai import node

@node(stream=True)
async def streaming_node(input: dict, callback):
    for chunk in process_chunks(input["data"]):
        await callback.acall(chunk)
    return {"result": "streaming complete"}
```

Two rules. `stream=True` tells GraphAI to inject the callback, and the node must declare a `callback` parameter to receive it.

### Streaming an LLM response

The common case:

```python
@node(stream=True)
async def llm_node(input: dict, callback):
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    stream = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": input["query"]},
        ],
        stream=True,
    )

    response_text = ""
    async for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            response_text += content
            await callback.acall(content)

    return {"response": response_text}
```

## Events

Everything that flows through the callback is a `GraphEvent`:

- `type` — what happened. One of `GraphEventType.START`, `END`, `START_NODE`, `END_NODE`, or `CALLBACK` (a streamed token).
- `identifier` — who emitted it. Defaults to `"graphai"`.
- `token` — the streamed content, for `CALLBACK` events.
- `params` — optional extra metadata.

Node boundaries and the end of the run are emitted as events too, so a consumer always knows where it is in the execution.

## Emitting events

```python
# async (preferred)
await callback.acall(token="chunk of text")

# sync, for non-async contexts
callback(token="chunk of text")
```

Both also take `type`, `identifier`, and `params`, so you can emit something other than a plain token:

```python
await callback.acall(
    token="search finished",
    type="tool_done",          # a GraphEventType, or your own string
    params={"tool": "search"},
)
```

You can mark node boundaries and close the stream yourself as well:

```python
await callback.start_node(node_name="my_node")
await callback.end_node(node_name="my_node")
await callback.close()
```

## Consuming the stream

`aiter()` is an async iterator over events. Start the graph as a background task, then read from the callback:

```python
import asyncio

cb = graph.get_callback()
task = asyncio.create_task(graph.execute(input={"input": {"query": "hello"}}, callback=cb))

async for event in cb.aiter():
    if event.type == "callback":
        print(event.token, end="", flush=True)

await task
```

Two things worth knowing. Pass the callback into `execute()` explicitly — that's what ties the stream to *that* run, and it keeps concurrent runs from bleeding into each other. And `aiter()` finishes when the stream closes, which happens when execution ends.

## Example: a streaming endpoint

`GraphEvent` objects play nicely with Starlette and FastAPI streaming responses, so a streaming API stays short:

```python
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from graphai import Graph, node
from graphai.callback import EventCallback

app = FastAPI()

@node(start=True, stream=True)
async def llm_stream(input: dict, callback):
    async for chunk in get_llm_response(input["query"]):
        await callback.acall(chunk)
    return {"status": "complete"}

@node(end=True)
async def final_node(input: dict):
    return {"status": "success"}

graph = Graph()
graph.set_callback(EventCallback)
graph.add_node(llm_stream).add_node(final_node)
graph.add_edge(llm_stream, final_node)

@app.post("/stream")
async def stream_endpoint(request: Request):
    data = await request.json()
    cb = graph.get_callback()
    asyncio.create_task(
        graph.execute(input={"input": {"query": data["query"]}}, callback=cb)
    )

    async def events():
        async for event in cb.aiter():
            if event.token:
                yield event.token

    return StreamingResponse(events(), media_type="text/event-stream")
```

## Good habits

1. **Stay async.** The callback is built on `asyncio`; prefer `acall` over the sync form.
2. **Pass the callback to `execute()`.** Don't share one instance across runs.
3. **Stream small chunks.** Tokens, not whole documents.
4. **Branch on `event.type`.** Handle node boundaries and the end event, not only tokens.

## Next steps

- [Graphs](graphs.md) — orchestrating execution
- [Nodes](nodes.md) — processing logic
- [State](state.md) — context across nodes
