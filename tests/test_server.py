import pytest
from fastmcp import Client

from talktome import registry
from talktome.server import mcp


@pytest.fixture(autouse=True)
def clear_state():
    registry.agents.clear()


@pytest.mark.asyncio
async def test_bridge_register():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "bridge_register", {"name": "backend", "path": "/api"}
        )
        assert "backend" in str(result)
        assert registry.is_registered("backend")


@pytest.mark.asyncio
async def test_bridge_register_multiple():
    async with Client(mcp) as client:
        await client.call_tool("bridge_register", {"name": "backend", "path": "/api"})
        await client.call_tool("bridge_register", {"name": "frontend", "path": "/web"})
        assert registry.count() == 2


@pytest.mark.asyncio
async def test_bridge_list_peers_empty():
    async with Client(mcp) as client:
        result = await client.call_tool("bridge_list_peers", {})
        assert "[]" in str(result)


@pytest.mark.asyncio
async def test_bridge_list_peers_after_register():
    async with Client(mcp) as client:
        await client.call_tool("bridge_register", {"name": "backend", "path": "/api"})
        result = await client.call_tool("bridge_list_peers", {})
        assert "backend" in str(result)
