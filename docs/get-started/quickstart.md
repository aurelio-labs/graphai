Let's build a small LLM-powered agent with GraphAI and the OpenAI API. By the end you'll have an agent that:

1. Decides whether to search for information or pull it from memory.
2. Runs the chosen action.
3. Writes a response to the user.

## Prerequisites

- Python 3.10+
- An OpenAI API key
- Some familiarity with async Python

## Install

```bash
pip install graphai-lib semantic-router
```

This example uses semantic-router's `OpenAILLM` for the LLM calls. GraphAI itself doesn't depend on it — swap in any client you like.

## Set up

```python
import os
from getpass import getpass
import ast
from graphai import router, node, Graph
from semantic_router.llms import OpenAILLM
from semantic_router.schema import Message
from pydantic import BaseModel, Field
import openai

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY") or getpass("Enter OpenAI API Key: ")

llm = OpenAILLM(name="gpt-4o-2024-08-06")  # use your preferred model
```

## Describe the tools

Two Pydantic models describe the agent's options. The LLM will pick one.

```python
class Search(BaseModel):
    query: str = Field(description="Search query for internet information")

class Memory(BaseModel):
    query: str = Field(description="Self-directed query to search information from your long-term memory")
```

## Define the nodes

Everything in GraphAI is a node: an async function that takes some input and returns a dict. A quick word on how data moves, because it shapes every node you write:

The dict you pass to `graph.execute()` *is* the graph's state. Each node receives only the parameters it declares, looked up by name from that state. So a node with an `input` parameter gets `state["input"]`, and a node with an `output` parameter gets `state["output"]`. Whatever a node returns is merged back into the state.

We'll keep the user's request under an `input` key throughout.

```python
@node(start=True)
async def node_start(input: dict):
    """Entry point for our graph."""
    return {"input": input}

@router
async def node_router(input: dict):
    """Routes the query to either search or memory."""
    query = input["query"]
    messages = [
        Message(
            role="system",
            content="You are a helpful assistant. Select the best route to answer the user query. ONLY choose one function.",
        ),
        Message(role="user", content=query),
    ]
    response = llm(
        messages=messages,
        function_schemas=[
            openai.pydantic_function_tool(Search),
            openai.pydantic_function_tool(Memory),
        ],
    )
    choice = ast.literal_eval(response)[0]
    return {
        "choice": choice["function_name"].lower(),
        "input": {**input, **choice["arguments"]},
    }

@node
async def memory(input: dict):
    """Retrieves information from memory."""
    # a real implementation would query a vector database
    return {"input": {"text": "The user is in Bali right now.", **input}}

@node
async def search(input: dict):
    """Searches for information."""
    # a real implementation would call a search API
    return {
        "input": {
            "text": "The most famous photo spot in Bali is the Uluwatu Temple.",
            **input,
        }
    }

@node
async def llm_node(input: dict):
    """Generates a response using the retrieved information."""
    chat_history = [
        Message(role=message["role"], content=message["content"])
        for message in input["chat_history"]
    ]

    messages = [
        Message(role="system", content="You are a helpful assistant."),
        *chat_history,
        Message(
            role="user",
            content=(
                f"Response to the following query from the user: {input['query']}\n"
                "Here is additional context. You can use it to answer the user query. "
                f"But do not directly reference it: {input.get('text', '')}."
            ),
        ),
    ]
    response = llm(messages=messages)
    return {"output": response}

@node(end=True)
async def node_end(output: str):
    """Exit point for our graph."""
    return {"output": output}
```

Notice the router. It returns a `"choice"` — the name of the node to run next — alongside the updated `input`. That's all a router needs to do.

And notice `node_end` declares `output`, not `input`, because the value it wants lives at `state["output"]` (that's what `llm_node` returned).

## Wire up the graph

```python
graph = Graph()

graph.add_node(node_start)
graph.add_node(node_router)
graph.add_node(memory)
graph.add_node(search)
graph.add_node(llm_node)
graph.add_node(node_end)

graph.add_edge(node_start, node_router)  # start -> router
graph.add_edge(search, llm_node)          # search -> llm
graph.add_edge(memory, llm_node)          # memory -> llm
graph.add_edge(llm_node, node_end)        # llm -> end

# the router needs no outgoing edges: its "choice" picks the next node
```

## Run it

```python
import asyncio

async def run_agent():
    input_data = {
        "query": "What's the best photo spot in Bali?",
        "chat_history": [
            {"role": "user", "content": "I'm planning a trip to Bali."},
            {"role": "assistant", "content": "That's wonderful! Bali is a beautiful destination with rich culture, stunning beaches, and vibrant scenery. How can I help with your trip planning?"},
        ],
    }

    result = await graph.execute(input={"input": input_data})
    print(result["output"])

asyncio.run(run_agent())
```

## What just happened

1. `node_start` took the request and stored it under `input`.
2. `node_router` asked the LLM whether to search or use memory, and returned that as its `choice`.
3. The chosen node — `search` or `memory` — added context to `input`.
4. `llm_node` wrote a response and stored it under `output`.
5. `node_end` returned it.

Swap out any node and the rest of the graph doesn't care. That's the point: change what a step does without changing the shape of the whole thing.
