## TypeError: object dict can't be used in 'await' expression

Every node in GraphAI must be an `async` function — the runtime awaits each one. Define a node with a plain `def` and you'll hit this:

```
Traceback (most recent call last):
  File "/app/.venv/lib/python3.13/site-packages/graphai/graph.py", line 351, in execute
    output = await current_node.invoke(input=state, state=self.state)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.13/site-packages/graphai/nodes/base.py", line 152, in invoke
    out = await instance.execute(**input)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.13/site-packages/graphai/nodes/base.py", line 74, in execute
    return await func(**params_dict)  # Pass only the necessary arguments
           ^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: object dict can't be used in 'await' expression
```

The fix is one word:

```python
# wrong
@node
def my_node(input: dict) -> dict:
    return {"output": "Hello, world!"}

# right
@node
async def my_node(input: dict) -> dict:
    return {"output": "Hello, world!"}
```
