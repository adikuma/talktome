import pytest
from fastmcp import Client

from talktome import queue, registry
from talktome.server import context_store, mcp


@pytest.fixture(autouse=True)
def clear_state():
    registry.agents.clear()
    queue.mailboxes.clear()
    context_store.clear()


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


@pytest.mark.asyncio
async def test_bridge_send_message():
    async with Client(mcp) as client:
        await client.call_tool("bridge_register", {"name": "backend", "path": "/api"})
        await client.call_tool("bridge_register", {"name": "frontend", "path": "/web"})
        result = await client.call_tool(
            "bridge_send_message",
            {"sender": "backend", "peer": "frontend", "message": "hello"},
        )
        assert "sent" in str(result)


@pytest.mark.asyncio
async def test_bridge_send_message_unknown_peer():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "bridge_send_message",
            {"sender": "backend", "peer": "nobody", "message": "hello"},
        )
        assert "not found" in str(result)


@pytest.mark.asyncio
async def test_bridge_read_mailbox():
    async with Client(mcp) as client:
        await client.call_tool("bridge_register", {"name": "backend", "path": "/api"})
        await client.call_tool("bridge_register", {"name": "frontend", "path": "/web"})
        await client.call_tool(
            "bridge_send_message",
            {"sender": "backend", "peer": "frontend", "message": "hey"},
        )
        result = await client.call_tool("bridge_read_mailbox", {"name": "frontend"})
        assert "hey" in str(result)


@pytest.mark.asyncio
async def test_bridge_read_mailbox_empty():
    async with Client(mcp) as client:
        result = await client.call_tool("bridge_read_mailbox", {"name": "nobody"})
        assert "[]" in str(result)


@pytest.mark.asyncio
async def test_bridge_share_context():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "bridge_share_context",
            {"owner": "backend", "key": "auth_url", "value": "/api/auth"},
        )
        assert "stored" in str(result)


@pytest.mark.asyncio
async def test_bridge_get_context():
    async with Client(mcp) as client:
        await client.call_tool(
            "bridge_share_context",
            {"owner": "backend", "key": "auth_url", "value": "/api/auth"},
        )
        result = await client.call_tool(
            "bridge_get_context", {"owner": "backend", "key": "auth_url"}
        )
        assert "/api/auth" in str(result)


@pytest.mark.asyncio
async def test_bridge_get_context_not_found():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "bridge_get_context", {"owner": "backend", "key": "nope"}
        )
        assert "no context" in str(result)


