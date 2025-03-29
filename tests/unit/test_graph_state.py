import pytest
from graphai import node, Graph


class TestGraphState:
    @pytest.mark.asyncio
    async def test_basic_state_access(self):
        """Test that nodes can access and modify the graph's internal state."""

        @node(start=True)
        async def node_counter_init(input: str, state: dict):
            """Initialize the counter in the graph state."""
            # Initialize a counter in the graph state
            state["counter"] = 1
            return {"message": "Counter initialized"}

        @node
        async def node_counter_increment(input: str, state: dict):
            """Increment the counter in the graph state."""
            # Increment the counter
            state["counter"] += 1
            return {"message": "Counter incremented"}

        @node
        async def node_counter_double(input: str, state: dict):
            """Double the counter in the graph state."""
            # Double the counter
            state["counter"] *= 2
            return {"message": "Counter doubled"}

        @node(end=True)
        async def node_counter_result(input: str, state: dict):
            """Return the final counter value."""
            # Return the counter value
            return {"result": state["counter"], "message": "Final counter"}

        # Create a graph with initial state
        graph = Graph(initial_state={"initialized": True})

        # Add nodes
        nodes = [
            node_counter_init,
            node_counter_increment,
            node_counter_double,
            node_counter_result,
        ]

        for i, node_fn in enumerate(nodes):
            graph.add_node(node_fn)
            if i > 0:
                graph.add_edge(nodes[i - 1], node_fn)

        # Execute the graph
        response = await graph.execute(input={"input": "test"})

        # Verify the counter was initialized, incremented, and doubled
        assert response["result"] == 4  # 1 -> 2 -> 4
        assert "message" in response
        assert response["message"] == "Final counter"

        # Verify we can access the graph state directly
        assert graph.get_state()["counter"] == 4
        assert graph.get_state()["initialized"]

    @pytest.mark.asyncio
    async def test_initial_state(self):
        """Test that the graph can be initialized with a state."""

        @node(start=True, end=True)
        async def node_check_state(input: str, state: dict):
            """Check that the initial state is accessible."""
            return {"initial_value": state["initial_value"]}

        # Create a graph with initial state
        initial_state = {"initial_value": 42}
        graph = Graph(initial_state=initial_state)

        # Add node
        graph.add_node(node_check_state)

        # Execute the graph
        response = await graph.execute(input={"input": "test"})

        # Verify the initial state was accessible
        assert response["initial_value"] == 42

    @pytest.mark.asyncio
    async def test_state_persistence_between_executions(self):
        """Test that the graph state persists between executions."""

        @node(start=True, end=True)
        async def node_increment_counter(input: str, state: dict):
            """Increment a counter in the graph state."""
            if "counter" not in state:
                state["counter"] = 0
            state["counter"] += 1
            return {"counter": state["counter"]}

        # Create a graph
        graph = Graph()

        # Add node
        graph.add_node(node_increment_counter)

        # First execution
        response1 = await graph.execute(input={"input": "test"})
        assert response1["counter"] == 1

        # The state is maintained in the graph object between executions
        assert graph.get_state()["counter"] == 1

        # Second execution will reuse the state without explicit resetting
        response2 = await graph.execute(input={"input": "test"})
        assert response2["counter"] == 2  # Incremented from 1 to 2

        # Reset the state to clear between executions if needed
        graph.reset_state()

        # After reset, the counter should start from 0 again
        response3 = await graph.execute(input={"input": "test"})
        assert response3["counter"] == 1  # Back to 1 after reset

    @pytest.mark.asyncio
    async def test_update_state_api(self):
        """Test the update_state API."""

        @node(start=True, end=True)
        async def node_read_state(input: str, state: dict):
            """Read values from the graph state."""
            return {
                "value1": state.get("value1", None),
                "value2": state.get("value2", None),
            }

        # Create a graph
        graph = Graph()

        # Add node
        graph.add_node(node_read_state)

        # Update state with the API
        graph.update_state({"value1": "hello", "value2": "world"})

        # Execute the graph
        response = await graph.execute(input={"input": "test"})

        # Verify the state was updated
        assert response["value1"] == "hello"
        assert response["value2"] == "world"

    @pytest.mark.asyncio
    async def test_complex_state_manipulation(self):
        """Test more complex state manipulation with nested data."""

        @node(start=True)
        async def node_init_complex_state(input: str, state: dict):
            """Initialize complex nested state."""
            state["users"] = {
                "alice": {"age": 30, "roles": ["admin", "editor"]},
                "bob": {"age": 25, "roles": ["user"]},
            }
            return {"message": "Complex state initialized"}

        @node
        async def node_modify_state(input: str, state: dict):
            """Modify the complex state."""
            # Add a new user
            state["users"]["charlie"] = {"age": 35, "roles": ["user", "reviewer"]}
            # Modify an existing user
            state["users"]["alice"]["roles"].append("owner")
            return {"message": "State modified"}

        @node(end=True)
        async def node_summarize_state(input: str, state: dict):
            """Summarize the state."""
            users = state["users"]
            return {
                "user_count": len(users),
                "admin_users": [
                    name for name, data in users.items() if "admin" in data["roles"]
                ],
            }

        # Create a graph
        graph = Graph()

        # Add nodes
        nodes = [node_init_complex_state, node_modify_state, node_summarize_state]

        for i, node_fn in enumerate(nodes):
            graph.add_node(node_fn)
            if i > 0:
                graph.add_edge(nodes[i - 1], node_fn)

        # Execute the graph
        response = await graph.execute(input={"input": "test"})

        # Verify the complex state manipulation
        assert response["user_count"] == 3
        assert response["admin_users"] == ["alice"]

        # Verify the state directly
        state = graph.get_state()
        assert len(state["users"]) == 3
        assert "charlie" in state["users"]
        assert len(state["users"]["alice"]["roles"]) == 3
        assert "owner" in state["users"]["alice"]["roles"]
