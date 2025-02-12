import pytest
from pydantic import BaseModel, Field
from graphai import router, node, Graph



class Search(BaseModel):
    query: str = Field(description="Search query for internet information")

class Memory(BaseModel):
    query: str = Field(description="Self-directed query to search information from your long term memory")


class TestGraph:
    @pytest.mark.asyncio
    async def test_linear_graph(self):
        @node(start=True)
        async def node_start(input: str):
            """Start node"""
            return {"input": input+"D"}
        
        @node
        async def node_a(input: str):
            """Node A"""
            return {"input": input+"E"}

        @node
        async def node_b(input: str):
            """Node B"""
            return {"input": input+"F"}

        @node(end=True)
        async def node_end(input: str):
            """End node"""
            return {"input": input+"G"}

        graph = Graph()

        nodes = [node_start, node_a, node_b, node_end]

        for i, node_fn in enumerate(nodes):
            graph.add_node(node_fn)
            if i > 0:
                graph.add_edge(nodes[i-1], node_fn)

        response = await graph.execute(input={"input": "ABC"})
        assert response == {"input": "ABCDEFG"}

    @pytest.mark.asyncio
    async def test_graph_with_name(self):
        @node(start=True, name="start")
        async def node_start(input: str):
            """Start node"""
            return {"input": input+"D"}
        
        @node(name="a")
        async def node_a(input: str):
            """Node A"""
            return {"input": input+"E"}
        
        assert node_a.name == "a"

        @node(name="b")
        async def node_b(input: str):
            """Node B"""
            return {"input": input+"F"}

        @node(end=True, name="end")
        async def node_end(input: str):
            """End node"""
            return {"input": input+"G"}

        graph = Graph()

        nodes = [
            (node_start, "start"),
            (node_a, "a"),
            (node_b, "b"),
            (node_end, "end")
        ]

        for i, (node_fn, name) in enumerate(nodes):
            graph.add_node(node_fn)
            if i > 0:
                # add each edge using the name only
                graph.add_edge(nodes[i-1][1], name)

        response = await graph.execute(input={"input": "ABC"})
        assert response == {"input": "ABCDEFG"}
