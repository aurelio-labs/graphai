from typing import Callable, List
from graphai.nodes.base import _Node


class Graph:
    def __init__(self):
        self.nodes = []
        self.edges = []
        self.start_node = None
        self.end_nodes = []

    def add_node(self, node):
        self.nodes.append(node)
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

    def add_edge(self, source: _Node, destination: _Node):
        # TODO add logic to check that source and destination are nodes
        # and they exist in the graph object already
        edge = Edge(source, destination)
        self.edges.append(edge)

    def add_router(self, source: _Node, router: _Node, destinations: List[_Node]):
        if not router.is_router:
            raise TypeError("A router object must be passed to the router parameter.")
        self.add_edge(source, router)
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
        print("Graph compiled successfully.")

    def _is_valid(self):
        # Implement validation logic, e.g., checking for cycles, disconnected components, etc.
        return True

    def execute(self, input):
        current_node = self.start_node
        state = input
        while current_node not in self.end_nodes:
            state = current_node.invoke(input=state)
            if current_node.is_router:
                # if we have a router node we let the router decide the next node
                next_node_name = str(state["choice"])
                del state["choice"]
                current_node = self._get_node_by_name(next_node_name)
            else:
                # otherwise, we have linear path
                current_node = self._get_next_node(current_node, state)
            if current_node.is_end:
                break
        return state

    def _get_node_by_name(self, node_name: str) -> _Node:
        for node in self.nodes:
            if node.name == node_name:
                return node
        raise Exception(f"Node with name {node_name} not found.")

    def _get_next_node(self, current_node, output):
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
            raise ImportError("NetworkX is required for visualization. Please install it with 'pip install networkx'.")

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError("Matplotlib is required for visualization. Please install it with 'pip install matplotlib'.")

        G = nx.DiGraph()

        for node in self.nodes:
            G.add_node(node.name)

        for edge in self.edges:
            G.add_edge(edge.source.name, edge.destination.name)

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
        max_x = max(abs(p[0]) for p in pos.values())
        max_y = max(abs(p[1]) for p in pos.values())
        scale = min(0.8 / max_x, 0.8 / max_y)
        pos = {node: (x * scale, y * scale) for node, (x, y) in pos.items()}

        # Draw the graph
        plt.figure(figsize=(8, 6))
        nx.draw(G, pos, with_labels=True, node_color='lightblue', 
                node_size=3000, font_size=8, font_weight='bold', 
                arrows=True, edge_color='gray', arrowsize=20)

        plt.axis('off')
        plt.show()


class Edge:
    def __init__(self, source, destination):
        self.source = source
        self.destination = destination