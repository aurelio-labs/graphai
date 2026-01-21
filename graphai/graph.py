from __future__ import annotations
import asyncio
from typing import Any, Iterable, Protocol
from graphlib import TopologicalSorter, CycleError

from graphai.callback import Callback
from graphai.utils import logger


# to fix mypy error
class _HasName(Protocol):
    name: str


class GraphError(Exception):
    pass


class GraphCompileError(GraphError):
    pass


class NodeProtocol(Protocol):
    """Protocol defining the interface of a decorated node."""

    name: str
    is_start: bool
    is_end: bool
    is_router: bool
    stream: bool

    async def invoke(
        self,
        input: dict[str, Any],
        callback: Callback | None = None,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


def _name_of(x: Any) -> str | None:
    """Return the node name if x is a str or has .name, else None."""
    if x is None:
        return None
    if isinstance(x, str):
        return x
    name = getattr(x, "name", None)
    return name if isinstance(name, str) else None


def _require_name(x: Any, kind: str) -> str:
    """Like _name_of, but raises a helpful compile error when missing."""
    s = _name_of(x)
    if s is None:
        raise GraphCompileError(
            f"Edge {kind} must be a node name (str) or object with .name"
        )
    return s


class Graph:
    def __init__(
        self, max_steps: int = 10, initial_state: dict[str, Any] | None = None
    ):
        self.nodes: dict[str, NodeProtocol] = {}
        self.edges: list[Any] = []
        self.start_node: NodeProtocol | None = None
        self.end_nodes: list[NodeProtocol] = []
        self.join_nodes: set[NodeProtocol] = set()
        self.Callback: type[Callback] = Callback
        self.max_steps = max_steps
        self.state = initial_state or {}

    # Allow getting and setting the graph's internal state
    def get_state(self) -> dict[str, Any]:
        """Get the current graph state.

        Returns:
            The current graph state.
        """
        return self.state

    def set_state(self, state: dict[str, Any]) -> Graph:
        """Set the graph state.

        Args:
            state: The new state to set for the graph.

        Returns:
            The graph instance.
        """
        self.state = state
        return self

    def update_state(self, values: dict[str, Any]) -> Graph:
        """Update the graph state with new values.

        Args:
            values: The new values to update the graph state with.
            
        Returns:
            The graph instance.
        """
        self.state.update(values)
        return self

    def reset_state(self) -> Graph:
        """Reset the graph state to an empty dict."""
        self.state = {}
        return self

    def add_node(self, node: NodeProtocol) -> Graph:
        """Adds a node to the graph.

        Args:
            node: The node to add to the graph.

        Raises:
            Exception: If a node with the same name already exists in the graph.
        """
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
        return self

    def _get_node(self, node_candidate: NodeProtocol | str) -> NodeProtocol:
        # first get node from graph
        if isinstance(node_candidate, str):
            node = self.nodes.get(node_candidate)
        else:
            # check if it's a node-like object by looking for required attributes
            if hasattr(node_candidate, "name"):
                node = self.nodes.get(node_candidate.name)
        if node is None:
            raise ValueError(f"Node with name '{node_candidate}' not found.")
        return node

    def add_edge(
        self, source: NodeProtocol | str, destination: NodeProtocol | str
    ) -> Graph:
        """Adds an edge between two nodes that already exist in the graph.

        Args:
            source: The source node or its name.
            destination: The destination node or its name.
        """
        source_node, destination_node = None, None
        # get source node from graph
        source_node = self._get_node(node_candidate=source)
        # get destination node from graph
        destination_node = self._get_node(node_candidate=destination)
        # create edge
        edge = Edge(source_node, destination_node)
        self.edges.append(edge)
        return self

    def add_router(
        self,
        sources: list[NodeProtocol],
        router: NodeProtocol,
        destinations: list[NodeProtocol],
    ) -> Graph:
        """Adds a router node, allowing for a decision to be made on which branch to
        follow based on the `choice` output of the router node.
        
        Args:
            sources: The list of source nodes for the router.
            router: The router node.
            destinations: The list of destination nodes for the router.
        """
        if not router.is_router:
            raise TypeError("A router object must be passed to the router parameter.")
        [self.add_edge(source, router) for source in sources]
        for destination in destinations:
            self.add_edge(router, destination)
        return self

    def set_start_node(self, node: NodeProtocol) -> Graph:
        self.start_node = node
        return self

    def set_end_node(self, node: NodeProtocol) -> Graph:
        self.end_node = node
        return self

    def compile(self, *, strict: bool = False) -> Graph:
        """Validate the graph:
        - exactly one start node present (or Graph.start_node set)
        - at least one end node present
        - all edges reference known nodes
        - all nodes reachable from the start
          (optional) **no cycles** when strict=True
        Returns self on success; raises GraphCompileError otherwise.
        """
        # nodes map
        nodes = getattr(self, "nodes", None)
        if not isinstance(nodes, dict) or not nodes:
            raise GraphCompileError("No nodes have been added to the graph")
        start_name: str | None = None
        # Bind and narrow the attribute for mypy
        start_node: _HasName | None = getattr(self, "start_node", None)
        if start_node is not None:
            start_name = start_node.name
        else:
            starts = [
                name
                for name, n in nodes.items()
                if getattr(n, "is_start", False) or getattr(n, "start", False)
            ]
            if len(starts) > 1:
                raise GraphCompileError(f"Multiple start nodes defined: {starts}")
            if len(starts) == 1:
                start_name = starts[0]
        if not start_name:
            raise GraphCompileError("No start node defined")
        # at least one end node
        if not any(
            getattr(n, "is_end", False) or getattr(n, "end", False)
            for n in nodes.values()
        ):
            raise GraphCompileError("No end node defined")
        # normalize edges into adjacency {src: set(dst)}
        raw_edges = getattr(self, "edges", None)
        adj: dict[str, set[str]] = {name: set() for name in nodes.keys()}
        def _add_edge(src: str, dst: str) -> None:
            if src not in nodes:
                raise GraphCompileError(f"Edge references unknown source node: {src}")
            if dst not in nodes:
                raise GraphCompileError(
                    f"Edge from {src} references unknown node(s): ['{dst}']"
                )
            adj[src].add(dst)
        if raw_edges is None:
            pass
        elif isinstance(raw_edges, dict):
            for raw_src, dsts in raw_edges.items():
                src = _require_name(raw_src, "source")
                dst_iter = (
                    [dsts]
                    if isinstance(dsts, (str,)) or getattr(dsts, "name", None)
                    else list(dsts)
                )
                for d in dst_iter:
                    dst = _require_name(d, "destination")
                    _add_edge(src, dst)
        else:
            # generic iterable of “edge records”
            try:
                iterator = iter(raw_edges)
            except TypeError:
                raise GraphCompileError("Internal edge map has unsupported type")
            for item in iterator:
                # (src, dst) OR (src, Iterable[dst])
                if isinstance(item, (tuple, list)) and len(item) == 2:
                    raw_src, rhs = item
                    src = _require_name(raw_src, "source")
                    if isinstance(rhs, str) or getattr(rhs, "name", None):
                        dst = _require_name(rhs, "destination")
                        _add_edge(src, rhs)
                    else:
                        # assume iterable of dsts (strings or node-like)
                        try:
                            for d in rhs:
                                dst = _require_name(d, "destination")
                                _add_edge(src, d)
                        except TypeError:
                            raise GraphCompileError(
                                "Edge tuple second item must be a destination or an iterable of destinations"
                            )
                    continue
                # Mapping-style: {"source": "...", "destination": "..."} or {"src": "...", "dst": "..."}
                if isinstance(item, dict):
                    src = _require_name(item.get("source", item.get("src")), "source")
                    dst = _require_name(
                        item.get("destination", item.get("dst")), "destination"
                    )
                    _add_edge(src, dst)
                    continue
                # Object with attributes .source/.destination (or .src/.dst)
                if hasattr(item, "source") or hasattr(item, "src"):
                    src = _require_name(
                        getattr(item, "source", getattr(item, "src", None)), "source"
                    )
                    dst = _require_name(
                        getattr(item, "destination", getattr(item, "dst", None)),
                        "destination",
                    )
                    _add_edge(src, dst)
                    continue
                # If none matched, this is an unsupported edge record
                raise GraphCompileError(
                    "Edges must be dict[str, Iterable[str]] or an iterable of (src, dst), "
                    "(src, Iterable[dst]), mapping{'source'/'destination'}, or objects with .source/.destination"
                )
        # reachability from start
        seen: set[str] = set()
        stack = [start_name]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(adj.get(cur, ()))
        unreachable = sorted(set(nodes.keys()) - seen)
        if unreachable:
            raise GraphCompileError(f"Unreachable nodes: {unreachable}")
        # optional cycle detection (strict mode)
        if strict:
            preds: dict[str, set[str]] = {n: set() for n in nodes.keys()}
            for s, ds in adj.items():
                for d in ds:
                    preds[d].add(s)
            try:
                list(TopologicalSorter(preds).static_order())
            except CycleError as e:
                raise GraphCompileError("cycle detected in graph (strict mode)") from e
        return self

    def _validate_output(self, output: dict[str, Any], node_name: str):
        if not isinstance(output, dict):
            raise ValueError(
                f"Expected dictionary output from node {node_name}. "
                f"Instead, got {type(output)} from '{output}'."
            )

    def _get_next_nodes(self, current_node: NodeProtocol) -> list[NodeProtocol]:
        """Return all successor nodes for the given node."""
        # we skip JoinEdge because they don't have regular destinations
        # and next nodes for those are handled in the execute method
        return [
            edge.destination
            for edge in self.edges
            if isinstance(edge, Edge) and edge.source == current_node
        ]

    async def _invoke_node(
        self, node: NodeProtocol, state: dict[str, Any], callback: Callback
    ):
        if node.stream:
            await callback.start_node(node_name=node.name)
            output = await node.invoke(input=state, callback=callback, state=self.state)
            self._validate_output(output=output, node_name=node.name)
            await callback.end_node(node_name=node.name)
        else:
            output = await node.invoke(input=state, state=self.state)
            self._validate_output(output=output, node_name=node.name)
        return output

    async def _execute_branch(
        self,
        current_node: NodeProtocol,
        state: dict[str, Any],
        callback: Callback,
        steps: int,
        stop_at_join: bool = False,
        branch_id: str | None = None,
    ):
        """Recursively execute a branch starting from `current_node`.
        When a node has multiple successors, run them concurrently and merge their outputs.

        Args:
            current_node: The node to start execution from
            state: The current state dict to pass to the node
            callback: The callback instance for events
            steps: Current step count for max_steps limit
            stop_at_join: If True, stop execution when reaching a join node
            branch_id: Unique identifier for this branch (used for parallel duplicate nodes)
        """
        while True:
            output = await self._invoke_node(current_node, state, callback)
            state = {**state, **output}  # merge node output into local state
            if current_node.is_end:
                break
            if current_node.is_router:
                if "choices" in output:
                    # for parallel execution, we collect next_nodes
                    choice_names = output["choices"]
                    del output["choices"]
                    next_nodes = [self._get_node_by_name(name) for name in choice_names]
                else:
                    # otherwise business as usual - get the next node only
                    next_node_name = str(output["choice"])
                    del output["choice"]
                    current_node = self._get_node_by_name(node_name=next_node_name)
                    continue
            else:
                # for sequential execution, we can just get the next node
                next_nodes = self._get_next_nodes(current_node)
            if stop_at_join and current_node in self.join_nodes:
                # for parallel branches, wait at JoinEdge until all branches are complete
                return state

            if not next_nodes:
                raise Exception(
                    f"No outgoing edge found for current node '{current_node.name}'."
                )
            if len(next_nodes) == 1:
                current_node = next_nodes[0]
            else:
                # Run each branch concurrently, assigning unique branch IDs
                # This ensures that even duplicate nodes (same node appearing multiple times)
                # are tracked as separate invocations
                branch_tasks = []
                for idx, n in enumerate(next_nodes):
                    # Create unique branch ID combining parent branch, node name, and index
                    new_branch_id = f"{branch_id or 'root'}_{n.name}_{idx}"
                    branch_tasks.append(
                        self._execute_branch(
                            current_node=n,
                            state=state.copy(),
                            callback=callback,
                            steps=steps + 1,
                            stop_at_join=True,  # force parallel branches to wait at JoinEdge
                            branch_id=new_branch_id,
                        )
                    )

                # Wait for ALL branches to complete (including duplicate node invocations)
                logger.debug(
                    f"Starting {len(branch_tasks)} parallel branches: "
                    f"{[n.name for n in next_nodes]}"
                )
                results = await asyncio.gather(*branch_tasks)
                logger.debug(f"All {len(results)} parallel branches completed")

                # merge states returned by each branch
                merged = state.copy()
                for res in results:
                    for k, v in res.items():
                        if k != "callback":
                            merged[k] = v
                if set(next_nodes) & self.join_nodes:
                    # if any of the next nodes are join nodes, we need to continue from the
                    # JoinEdge.destination node
                    join_edge = next(
                        (
                            e for e in self.edges if isinstance(e, JoinEdge)
                            and any(n in e.sources for n in next_nodes)
                        ),
                        None
                    )
                    if not join_edge:
                        raise Exception("No JoinEdge found for next_nodes")
                    # set current_node (for next iteration) to the JoinEdge.destination
                    current_node = join_edge.destination
                    # continue to the destination node with our merged state
                    state = merged
                    continue
                else:
                    # if this happens we have multiple branches that do not join so we
                    # can just return the merged states
                    return merged
            steps += 1
            if steps >= self.max_steps:
                raise Exception(
                    f"Max steps reached: {self.max_steps}. You can modify this by setting `max_steps` when initializing the Graph object."
                )
        return state

    async def execute(self, input: dict[str, Any], callback: Callback | None = None):
        # TODO JB: may need to add init callback here to init the queue on every new execution
        if callback is None:
            callback = self.get_callback()

        # Type assertion to tell the type checker that start_node is not None after compile()
        assert self.start_node is not None, "Graph must be compiled before execution"

        state = input
        result = await self._execute_branch(self.start_node, state, callback, 0)
        # TODO JB: may need to add end callback here to close the queue for every execution
        if callback and "callback" in result:
            await callback.close()
            del result["callback"]
        return result

    async def execute_many(
        self, inputs: Iterable[dict[str, Any]], *, concurrency: int = 5
    ) -> list[Any]:
        """Execute the graph on many inputs concurrently.

        :param inputs: An iterable of input dicts to feed into the graph.
        :type inputs: Iterable[dict]
        :param concurrency: Maximum number of graph executions to run at once.
        :type concurrency: int
        :param state: Optional shared state to pass to each execution.
            If you want isolated state per execution, pass None
            and the graph's normal semantics will apply.
        :type state: Optional[Any]
        :returns: The list of results in the same order as ``inputs``.
        :rtype: list[Any]
        """

        sem = asyncio.Semaphore(concurrency)

        async def _run_one(inp: dict[str, Any]) -> Any:
            async with sem:
                return await self.execute(input=inp)

        tasks = [asyncio.create_task(_run_one(i)) for i in inputs]
        return await asyncio.gather(*tasks)

    def get_callback(self):
        """Get a new instance of the callback class.

        :return: A new instance of the callback class.
        :rtype: Callback
        """
        callback = self.Callback()
        return callback

    def set_callback(self, callback_class: type[Callback]) -> "Graph":
        """Set the callback class that is returned by the `get_callback` method and used
        as the default callback when no callback is passed to the `execute` method.

        :param callback_class: The callback class to use as the default callback.
        :type callback_class: type[Callback]
        """
        self.Callback = callback_class
        return self

    def _get_node_by_name(self, node_name: str) -> NodeProtocol:
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
            if isinstance(edge, Edge) and edge.source == current_node:
                return edge.destination
            # we skip JoinEdge because they don't have regular destinations
            # and next nodes for those are handled in the execute method
        raise Exception(
            f"No outgoing edge found for current node '{current_node.name}'."
        )

    def add_parallel(
        self, source: NodeProtocol | str, destinations: list[NodeProtocol | str]
    ):
        """Add multiple outgoing edges from a single source node to be executed in parallel.

        Args:
            source: The source node for the parallel branches.
            destinations: The list of destination nodes for the parallel branches.
        """
        for dest in destinations:
            self.add_edge(source, dest)
        return self

    def add_join(
        self, sources: list[NodeProtocol | str], destination: NodeProtocol | str
    ):
        """Joins multiple parallel branches into a single branch.
        
        Args:
            sources: The list of source nodes for the join.
            destination: The destination node for the join.
        """
        # get source nodes from graph
        source_nodes = [self._get_node(node_candidate=source) for source in sources]
        # get destination node from graph
        destination_node = self._get_node(node_candidate=destination)
        # create join edge
        edge = JoinEdge(source_nodes, destination_node)
        self.edges.append(edge)
        self.join_nodes.update(source_nodes)
        return self

    def visualize(self, *, save_path: str | None = None):
        """Render the current graph. If matplotlib is not installed,
        raise a helpful error telling users to install the viz extra.
        Optionally save to a file via `save_path`.
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError as e:
            raise ImportError(
                "Graph visualization requires matplotlib. Install it with: `pip install matplotlib`"
            ) from e

        try:
            import networkx as nx
        except ImportError as e:
            raise ImportError(
                "NetworkX is required for visualization. Please install it with `pip install networkx`."
            ) from e

        G: Any = nx.DiGraph()

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
            pos: dict[Any, tuple[float, float]] = {}
            for i, generation in enumerate(generations):
                x = 0
                for node in generation:
                    pos[node] = (float(x), float(y_coord[node]))
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

        if save_path:
            plt.savefig(save_path, bbox_inches="tight")
        else:
            plt.axis("off")
            plt.show()
        plt.close()


class Edge:
    def __init__(self, source, destination):
        self.source = source
        self.destination = destination

class JoinEdge:
    def __init__(self, sources, destination):
        self.sources = sources
        self.destination = destination
