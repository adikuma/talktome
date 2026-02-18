import pytest
import pytest_asyncio
from fastmcp import Client
from httpx import ASGITransport, AsyncClient

from talktome import db
from talktome.server import mcp


@pytest.fixture(autouse=True)
def clear_state():
    db.reset()


# db layer tests


def test_create_task():
    task = db.create_task("t1", "backend", "run tests")
    assert task["id"] == "t1"
    assert task["agent"] == "backend"
    assert task["description"] == "run tests"
    assert task["status"] == "pending"
    assert task["result"] is None
    assert "created_at" in task
    assert "updated_at" in task


def test_get_task():
    db.create_task("t1", "backend", "run tests")
    task = db.get_task("t1")
    assert task is not None
    assert task["id"] == "t1"
    assert task["agent"] == "backend"


def test_get_task_not_found():
    assert db.get_task("nope") is None


def test_get_tasks():
    db.create_task("t1", "backend", "first")
    db.create_task("t2", "frontend", "second")
    tasks = db.get_tasks()
    assert len(tasks) == 2


def test_get_agent_tasks():
    db.create_task("t1", "backend", "first")
    db.create_task("t2", "frontend", "second")
    db.create_task("t3", "backend", "third")
    tasks = db.get_agent_tasks("backend")
    assert len(tasks) == 2
    assert all(t["agent"] == "backend" for t in tasks)


def test_get_agent_tasks_empty():
    assert db.get_agent_tasks("nobody") == []


def test_get_pending_tasks():
    db.create_task("t1", "backend", "first")
    db.create_task("t2", "backend", "second")
    db.update_task("t1", status="running")
    pending = db.get_pending_tasks("backend")
    assert len(pending) == 1
    assert pending[0]["id"] == "t2"


def test_update_task_status():
    db.create_task("t1", "backend", "run tests")
    task = db.update_task("t1", status="running")
    assert task["status"] == "running"
    assert task["id"] == "t1"


def test_update_task_result():
    db.create_task("t1", "backend", "run tests")
    task = db.update_task("t1", status="done", result="all passed")
    assert task["status"] == "done"
    assert task["result"] == "all passed"


def test_update_task_not_found():
    assert db.update_task("nope", status="done") is None


# rest endpoint tests


@pytest_asyncio.fixture
async def http_client():
    app = mcp.http_app(path="/mcp")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_task_create_rest(http_client):
    resp = await http_client.post("/task", json={"agent": "backend", "description": "run tests"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent"] == "backend"
    assert data["description"] == "run tests"
    assert data["status"] == "pending"
    assert "id" in data


@pytest.mark.asyncio
async def test_task_create_rest_missing_fields(http_client):
    resp = await http_client.post("/task", json={"agent": ""})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_tasks_list_rest(http_client):
    db.create_task("t1", "backend", "first")
    db.create_task("t2", "frontend", "second")
    resp = await http_client.get("/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_tasks_agent_rest(http_client):
    db.create_task("t1", "backend", "first")
    db.create_task("t2", "frontend", "second")
    resp = await http_client.get("/tasks/backend")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["agent"] == "backend"


@pytest.mark.asyncio
async def test_task_update_rest(http_client):
    db.create_task("t1", "backend", "run tests")
    resp = await http_client.patch("/task/t1", json={"status": "running"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_task_update_rest_with_result(http_client):
    db.create_task("t1", "backend", "run tests")
    resp = await http_client.patch("/task/t1", json={"status": "done", "result": "all passed"})
    data = resp.json()
    assert data["status"] == "done"
    assert data["result"] == "all passed"


@pytest.mark.asyncio
async def test_task_update_rest_not_found(http_client):
    resp = await http_client.patch("/task/nope", json={"status": "done"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_tasks_pending_rest(http_client):
    db.create_task("t1", "backend", "first")
    db.create_task("t2", "backend", "second")
    db.update_task("t1", status="done")
    resp = await http_client.get("/tasks/backend/pending")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "t2"


# mcp tool tests


@pytest.mark.asyncio
async def test_bridge_create_task():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "bridge_create_task",
            {"agent": "backend", "description": "run tests"},
        )
        assert "backend" in str(result)
        assert "pending" in str(result)


@pytest.mark.asyncio
async def test_bridge_get_tasks():
    db.create_task("t1", "backend", "first")
    async with Client(mcp) as client:
        result = await client.call_tool("bridge_get_tasks", {"agent": "backend"})
        assert "first" in str(result)


@pytest.mark.asyncio
async def test_bridge_get_tasks_all():
    db.create_task("t1", "backend", "first")
    db.create_task("t2", "frontend", "second")
    async with Client(mcp) as client:
        result = await client.call_tool("bridge_get_tasks", {})
        assert "first" in str(result)
        assert "second" in str(result)


@pytest.mark.asyncio
async def test_bridge_update_task():
    db.create_task("t1", "backend", "run tests")
    async with Client(mcp) as client:
        result = await client.call_tool(
            "bridge_update_task",
            {"task_id": "t1", "status": "done", "result": "all passed"},
        )
        assert "done" in str(result)


@pytest.mark.asyncio
async def test_bridge_update_task_not_found():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "bridge_update_task",
            {"task_id": "nope", "status": "done"},
        )
        assert "not found" in str(result)


# activity logging for tasks


@pytest.mark.asyncio
async def test_task_activity_logged(http_client):
    await http_client.post("/task", json={"agent": "backend", "description": "run tests"})
    resp = await http_client.get("/activity")
    data = resp.json()
    events = [e["event"] for e in data]
    assert "task_created" in events


@pytest.mark.asyncio
async def test_task_update_activity_logged(http_client):
    db.create_task("t1", "backend", "run tests")
    await http_client.patch("/task/t1", json={"status": "done"})
    resp = await http_client.get("/activity")
    data = resp.json()
    events = [e["event"] for e in data]
    assert "task_updated" in events
