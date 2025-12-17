The `Graph` is the central orchestration component in GraphAI. It connects `Nodes` and `Routers` into a coherent workflow and manages the execution flow.

## Graph Basics

A graph consists of:

- **Nodes**: Processing units that perform specific tasks
- **Edges**: Connections between nodes that define the flow of data
- **State**: Shared context that persists throughout the execution

## Creating a Graph

```python
from graphai import Graph

# Create a graph with default settings
graph = Graph()

# Create a graph with custom max steps and initial state
graph = Graph(max_steps=20, initial_state={"history": []})
```

### Parameters

- `max_steps` (int, default=10): Maximum number of steps to prevent infinite loops
- `initial_state` (Dict[str, Any], optional): Initial state for the graph execution

## Adding Nodes

Nodes are the building blocks of your graph. Each node represents a discrete processing step:

```python
# Add a node to the graph
graph.add_node(my_node())

# Add multiple nodes
graph.add_node(node_a())
graph.add_node(node_b())
graph.add_node(node_c())
```

Nodes can be:
- **Start nodes**: Entry points to the graph (only one allowed)
- **End nodes**: Exit points from the graph (multiple allowed)
- **Regular nodes**: Intermediate processing steps
- **Router nodes**: Decision points that determine execution flow

## Connecting Nodes with Edges

Edges define how data flows between nodes:

```python
# Connect two nodes
graph.add_edge(source_node, destination_node)

# Can use node names instead of node objects
graph.add_edge("node_a", "node_b")
```

For linear workflows, you simply connect nodes in sequence:

```python
graph.add_edge(node_a, node_b)
graph.add_edge(node_b, node_c)
```

## Working with Routers

Routers are special nodes that determine the next node to execute based on their output:

```python
# Add a router with its sources and destinations
graph.add_router(
    sources=[node_a],  # Nodes that can lead to the router
    router=my_router(), # The router node itself
    destinations=[node_b, node_c]  # Possible destinations from the router
)
```

The router must return a dictionary containing a `"choice"` key with the name of the next node to execute:

```python
@router
async def my_router(input: dict):
    # Decision logic
    if some_condition:
        return {"choice": "node_b", "data": processed_data}
    else:
        return {"choice": "node_c", "data": processed_data}
```

## Graph Execution

To execute a graph:

```python
import asyncio

async def run_graph():
    # Define initial input
    input_data = {"query": "Hello, world!"}
    
    # Execute the graph
    result = await graph.execute(input_data)
    
    return result

# Run the async function
result = asyncio.run(run_graph())
```

### Execution Flow

1. The graph starts execution at the designated start node
2. Each node processes the input and returns an output
3. The output is merged with the current state and passed to the next node
4. If a router node is encountered, its `"choice"` output determines the next node
5. Execution continues until an end node is reached or max_steps is exceeded

## State Management

The graph maintains a state dictionary that persists throughout execution:

```python
# Get the current state
state = graph.get_state()

# Set the state
graph.set_state({"history": [], "context": "some context"})

# Update the state
graph.update_state({"new_key": "new_value"})

# Reset the state
graph.reset_state()
```

Each node receives the current state as an optional parameter:

```python
@node
async def my_node(input: dict, state: dict):
    # Access the state
    history = state.get("history", [])
    
    # Update the state (changes won't persist outside this node)
    # For persistent changes, return them in the output
    return {"output": result, "history": history + [result]}
```

## Graph Validation

Before execution, you can validate that your graph is properly configured:

```python
# Compile will raise exceptions if the graph is invalid
graph.compile()
```

The compile method checks for:
- Presence of a start node
- Presence of at least one end node
- Graph validity (e.g., no disconnected nodes)

## Visualization

GraphAI provides a method to visualize your graph (requires matplotlib and networkx):

```python
# Visualize the graph
graph.visualize()
```

This generates a visual representation of your graph, making it easier to understand complex workflows.

## Next Steps

- Learn about [Nodes](nodes.md) to understand how to build processing units
- Explore [Parallel Execution](parallel-execution.md) for concurrent branch processing
- Explore [State](state.md) management for maintaining context
- Check out [Callbacks](callbacks.md) for implementing streaming