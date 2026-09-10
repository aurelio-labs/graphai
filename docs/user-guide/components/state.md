State is the dict that carries data through a run. It's how a node knows what earlier nodes did.

## The basics

The state dict:

1. Starts as whatever you pass to `execute()` — or `initial_state`, if you set one.
2. Lives for the whole run.
3. Is readable by any node that asks for it.
4. Grows as nodes return values.

## Seeding state

Set an initial state when you create the graph:

```python
from graphai import Graph

graph = Graph(initial_state={
    "history": [],
    "context": "initial context",
    "metadata": {
        "user_id": "user123",
        "session_start": 1625097600,
    },
})
```

Leave it out and the state starts empty.

## The state methods

```python
current = graph.get_state()
graph.set_state({"new_state": "value"})       # replace
graph.update_state({"additional": "data"})    # merge
graph.reset_state()                           # clear
```

## Reading state in a node

Declare a `state` parameter and GraphAI passes it in:

```python
from graphai import node

@node
async def stateful_node(input: dict, state: dict):
    history = state.get("history", [])
    context = state.get("context", "")
    processed = process_with_context(input["data"], context)
    return {"result": processed}
```

## Changing state

Two ways, and both persist.

**Return it.** Any key in the returned dict is merged into the state. This is the clearest way to hand data to the next node:

```python
@node
async def update_history(input: dict, state: dict):
    history = state.get("history", [])
    return {
        "result": process(input["query"]),
        "history": history + [input["query"]],
    }
```

**Mutate it.** The `state` a node receives is the graph's actual state object, so in-place changes stick:

```python
@node
async def append_history(input: dict, state: dict):
    state.setdefault("history", []).append(input["query"])
    return {}
```

Returning keys is usually the better habit — it's explicit, and it's easy to see what a node contributes. Mutation is handy for accumulating into an existing list or dict.

## State vs. input

There's no separate "input" mechanism. The dict you pass to `execute()` *is* the initial state, and each node receives whichever keys it declares as parameters. By convention the request goes under an `input` key, which is why so many nodes declare `input: dict` — but that's just a key like any other.

```python
@node
async def process_with_both(input: dict, state: dict):
    query = input["query"]                 # state["input"]["query"]
    history = state.get("history", [])     # the whole state
    result = process_with_history(query, history)
    return {"result": result, "history": history + [query]}
```

## Persisting across runs

State lives as long as the graph object. To carry it between runs, save and restore it:

```python
result = await graph.execute(input={"input": input_data})
saved = graph.get_state()
store_state(saved)

# later
graph.set_state(load_state())
```

## Scope

State belongs to a graph instance. Two graphs never share it:

```python
graph1 = Graph(initial_state={"id": "graph1"})
graph2 = Graph(initial_state={"id": "graph2"})

graph1.update_state({"value": 1})
graph2.update_state({"value": 2})
```

## Good habits

1. **Keep it serializable** — dicts, lists, strings, numbers — so you can save it.
2. **Be selective.** Only put things in state that later nodes actually need.
3. **Write down the shape.** A documented state structure saves everyone time.
4. **Watch the size.** Don't let it grow without bound in long-running apps.

## Next steps

- [Graphs](graphs.md) — orchestrating a run
- [Nodes](nodes.md) — processing logic
- [Callbacks](callbacks.md) — streaming
