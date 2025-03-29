from typing import List, Dict, Any, Optional
from graphai.nodes.base import _Node
from graphai.callback import Callback
from graphai.utils import logger


class Graph:
    def __init__(
        self, max_steps: int = 10, initial_state: Optional[Dict[str, Any]] = None
    ):
        self.nodes: Dict[str, _Node] = {}
        self.edges: List[Any] = []
        self.start_node: Optional[_Node] = None
        self.end_nodes: List[_Node] = []
        self.Callback = Callback
        self.callback = None
        self.max_steps = max_steps
        self.state = initial_state or {}

    # Allow getting and setting the graph's internal state
    def get_state(self) -> Dict[str, Any]:
        """Get the current graph state."""
        return self.state

    def set_state(self, state: Dict[str, Any]):
        """Set the graph state."""
        self.state = state

    def update_state(self, values: Dict[str, Any]):
        """Update the graph state with new values."""
        self.state.update(values)

    def reset_state(self):
        """Reset the graph state to an empty dict."""
        self.state = {}

    def add_node(self, node):
        if node.name in self.nodes:
            raise Exception(f"Node with name '{node.name}' already exists.")
        self.nodes[node.name] = node
        if node.is_start:
            if self.start_node is not None:
                raise Exception(
                    "Multiple start nodes are not allowed. Start node "
                    f"'{self.start_node.name}' already exists, so new start "
                    f"node '{node.name}' can not be added to the graph."
                )
            self.start_node = node
        if node.is_end:
            self.end_nodes.append(node)

    def add_edge(self, source: _Node | str, destination: _Node | str):
        """Adds an edge between two nodes that already exist in the graph.

        Args:
            source: The source node or its name.
            destination: The destination node or its name.
        """
        source_node, destination_node = None, None
        # get source node from graph
        if isinstance(source, str):
            source_node = self.nodes.get(source)
        else:
            # Check if it's a node-like object by looking for required attributes
            if hasattr(source, "name"):
                source_node = self.nodes.get(source.name)
        if source_node is None:
            raise ValueError(
                f"Node with name '{source.name if hasattr(source, 'name') else source}' not found."
            )
        # get destination node from graph
        if isinstance(destination, str):
            destination_node = self.nodes.get(destination)
        else:
            # Check if it's a node-like object by looking for required attributes
            if hasattr(destination, "name"):
                destination_node = self.nodes.get(destination.name)
        if destination_node is None:
            raise ValueError(
                f"Node with name '{destination.name if hasattr(destination, 'name') else destination}' not found."
            )
        edge = Edge(source_node, destination_node)
        self.edges.append(edge)

    def add_router(
        self, sources: list[_Node], router: _Node, destinations: List[_Node]
    ):
        if not router.is_router:
            raise TypeError("A router object must be passed to the router parameter.")
        [self.add_edge(source, router) for source in sources]
        for destination in destinations:
            self.add_edge(router, destination)

    def set_start_node(self, node: _Node):
        self.start_node = node

    def set_end_node(self, node: _Node):
        self.end_node = node

    def compile(self):
        if not self.start_node:
            raise Exception("Start node not defined.")
        if not self.end_nodes:
            raise Exception("No end nodes defined.")
        if not self._is_valid():
            raise Exception("Graph is not valid.")

    def _is_valid(self):
        # Implement validation logic, e.g., checking for cycles, disconnected components, etc.
        return True

    def _validate_output(self, output: Dict[str, Any], node_name: str):
        if not isinstance(output, dict):
            raise ValueError(
                f"Expected dictionary output from node {node_name}. "
                f"Instead, got {type(output)} from '{output}'."
            )

    async def execute(self, input):
        # TODO JB: may need to add init callback here to init the queue on every new execution
        if self.callback is None:
            self.callback = self.get_callback()
        current_node = self.start_node
        state = input
        # Don't reset the graph state if it was initialized with initial_state
        steps = 0
        while True:
            # we invoke the node here
            if current_node.stream:
                # add callback tokens and param here if we are streaming
                await self.callback.start_node(node_name=current_node.name)
                # Include graph's internal state in the node execution context
                output = await current_node.invoke(
                    input=state, callback=self.callback, state=self.state
                )
                self._validate_output(output=output, node_name=current_node.name)
                await self.callback.end_node(node_name=current_node.name)
            else:
                # Include graph's internal state in the node execution context
                output = await current_node.invoke(input=state, state=self.state)
                self._validate_output(output=output, node_name=current_node.name)
            # add output to state
            state = {**state, **output}
            if current_node.is_end:
                # finish loop if this was an end node
                break
            if current_node.is_router:
                # if we have a router node we let the router decide the next node
                next_node_name = str(output["choice"])
                del output["choice"]
                current_node = self._get_node_by_name(node_name=next_node_name)
            else:
                # otherwise, we have linear path
                current_node = self._get_next_node(current_node=current_node)
            steps += 1
            if steps >= self.max_steps:
                raise Exception(
                    f"Max steps reached: {self.max_steps}. You can modify this "
                    "by setting `max_steps` when initializing the Graph object."
                )
        # TODO JB: may need to add end callback here to close the queue for every execution
        if self.callback and "callback" in state:
            await self.callback.close()
            del state["callback"]
        return state

    def get_callback(self):
        self.callback = self.Callback()
        return self.callback

    def _get_node_by_name(self, node_name: str) -> _Node:
        """Get a node by its name.

        Args:
            node_name: The name of the node to find.

        Returns:
            The node with the given name.

        Raises:
            Exception: If no node with the given name is found.
        """
        node = self.nodes.get(node_name)
        if node is None:
            raise Exception(f"Node with name {node_name} not found.")
        return node

    def _get_next_node(self, current_node):
        for edge in self.edges:
            if edge.source == current_node:
                return edge.destination
        raise Exception(
            f"No outgoing edge found for current node '{current_node.name}'."
        )

    def visualize(self):
        try:
            import networkx as nx
        except ImportError:
            raise ImportError(
                "NetworkX is required for visualization. Please install it with 'pip install networkx'."
            )

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError(
                "Matplotlib is required for visualization. Please install it with 'pip install matplotlib'."
            )

        G = nx.DiGraph()

        for node in self.nodes.values():
            G.add_node(node.name)

        for edge in self.edges:
            G.add_edge(edge.source.name, edge.destination.name)

        if nx.is_directed_acyclic_graph(G):
            logger.info(
                "The graph is acyclic. Visualization will use a topological layout."
            )
            # Use topological layout if acyclic
            # Compute the topological generations
            generations = list(nx.topological_generations(G))
            y_max = len(generations)

            # Create a dictionary to store the y-coordinate for each node
            y_coord = {}
            for i, generation in enumerate(generations):
                for node in generation:
                    y_coord[node] = y_max - i - 1

            # Set up the layout
            pos = {}
            for i, generation in enumerate(generations):
                x = 0
                for node in generation:
                    pos[node] = (x, y_coord[node])
                    x += 1

            # Center each level horizontally
            for i, generation in enumerate(generations):
                x_center = sum(pos[node][0] for node in generation) / len(generation)
                for node in generation:
                    pos[node] = (pos[node][0] - x_center, pos[node][1])

            # Scale the layout
            max_x = max(abs(p[0]) for p in pos.values()) if pos else 1
            max_y = max(abs(p[1]) for p in pos.values()) if pos else 1
            if max_x > 0 and max_y > 0:
                scale = min(0.8 / max_x, 0.8 / max_y)
                pos = {node: (x * scale, y * scale) for node, (x, y) in pos.items()}

        else:
            print(
                "Warning: The graph contains cycles. Visualization will use a spring layout."
            )
            pos = nx.spring_layout(G, k=1, iterations=50)

        plt.figure(figsize=(8, 6))
        nx.draw(
            G,
            pos,
            with_labels=True,
            node_color="lightblue",
            node_size=3000,
            font_size=8,
            font_weight="bold",
            arrows=True,
            edge_color="gray",
            arrowsize=20,
        )

        plt.axis("off")
        plt.show()


class Edge:
    def __init__(self, source, destination):
        self.source = source
        self.destination = destination
