import pytest
import pytest_asyncio
from fastmcp import Client
from httpx import ASGITransport, AsyncClient

from talktome import db, queue, registry
from talktome.server import mcp


@pytest.fixture(autouse=True)
def clear_state():
    db.reset()


@pytest.mark.asyncio
async def test_bridge_register():
    async with Client(mcp) as client:
        result = await client.call_tool("bridge_register", {"name": "backend", "path": "/api"})
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
        result = await client.call_tool("bridge_get_context", {"owner": "backend", "key": "nope"})
        assert "no context" in str(result)


@pytest_asyncio.fixture
async def http_client():
    app = mcp.http_app(path="/mcp")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_health(http_client):
    resp = await http_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_peek_empty(http_client):
    resp = await http_client.get("/peek/nobody")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data["messages"] == []


@pytest.mark.asyncio
async def test_peek_with_messages(http_client):
    queue.send("alice", "bob", "hello")
    resp = await http_client.get("/peek/bob")
    data = resp.json()
    assert data["count"] == 1
    assert data["messages"][0]["message"] == "hello"
    # peek should not drain
    assert queue.count("bob") == 1


@pytest.mark.asyncio
async def test_agents_endpoint(http_client):
    registry.register("backend", "/api")
    registry.register("frontend", "/web")
    queue.send("backend", "frontend", "hi")
    resp = await http_client.get("/agents")
    data = resp.json()
    assert len(data) == 2
    frontend = [a for a in data if a["name"] == "frontend"][0]
    assert frontend["mailbox_count"] == 1


@pytest.mark.asyncio
async def test_activity_endpoint(http_client):
    async with Client(mcp) as client:
        await client.call_tool("bridge_register", {"name": "backend", "path": "/api"})
    resp = await http_client.get("/activity")
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["event"] == "register"


@pytest.mark.asyncio
async def test_dashboard(http_client):
    resp = await http_client.get("/")
    assert resp.status_code == 200
    assert "talktome" in resp.text
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_send_rest(http_client):
    registry.register("alice", "/a")
    registry.register("bob", "/b")
    resp = await http_client.post(
        "/send", json={"sender": "alice", "peer": "bob", "message": "hey"}
    )
    assert resp.status_code == 200
    assert "sent" in resp.json()["result"]
    assert queue.count("bob") == 1


@pytest.mark.asyncio
async def test_send_rest_unknown_peer(http_client):
    resp = await http_client.post(
        "/send", json={"sender": "alice", "peer": "nobody", "message": "hey"}
    )
    assert "not found" in resp.json()["result"]


@pytest.mark.asyncio
async def test_send_rest_missing_peer(http_client):
    resp = await http_client.post("/send", json={"sender": "alice", "peer": "", "message": "hey"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_read_rest(http_client):
    queue.send("alice", "bob", "hello")
    queue.send("alice", "bob", "world")
    resp = await http_client.get("/read/bob")
    data = resp.json()
    assert len(data) == 2
    assert data[0]["message"] == "hello"
    # read drains the mailbox
    assert queue.count("bob") == 0


@pytest.mark.asyncio
async def test_read_rest_empty(http_client):
    resp = await http_client.get("/read/nobody")
    assert resp.json() == []


@pytest.mark.asyncio
async def test_context_store_rest(http_client):
    resp = await http_client.post(
        "/context", json={"owner": "alice", "key": "url", "value": "/api/v1"}
    )
    assert "stored" in resp.json()["result"]


@pytest.mark.asyncio
async def test_context_get_rest(http_client):
    resp = await http_client.post(
        "/context", json={"owner": "alice", "key": "url", "value": "/api/v1"}
    )
    assert resp.status_code == 200
    resp = await http_client.get("/context/alice/url")
    assert resp.json()["value"] == "/api/v1"


@pytest.mark.asyncio
async def test_context_get_rest_not_found(http_client):
    resp = await http_client.get("/context/alice/nope")
    assert "error" in resp.json()


@pytest.mark.asyncio
async def test_wait_for_reply_via_peek_and_read(http_client):
    registry.register("alice", "/a")
    registry.register("bob", "/b")
    # peek shows empty initially
    resp = await http_client.get("/peek/bob")
    assert resp.json()["count"] == 0
    # send a message
    queue.send("alice", "bob", "ping")
    # peek shows 1 message (non-draining)
    resp = await http_client.get("/peek/bob")
    assert resp.json()["count"] == 1
    assert resp.json()["messages"][0]["message"] == "ping"
    # peek again - still there (not drained)
    resp = await http_client.get("/peek/bob")
    assert resp.json()["count"] == 1
    # read drains it
    resp = await http_client.get("/read/bob")
    assert len(resp.json()) == 1
    # now peek shows empty
    resp = await http_client.get("/peek/bob")
    assert resp.json()["count"] == 0
