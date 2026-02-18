import json
import os
import tempfile

import pytest
from httpx import ASGITransport, AsyncClient

from talktome import db, registry
from talktome.server import (
    decode_claude_path,
    mcp,
    read_session_meta,
)


@pytest.fixture(autouse=True)
def clear_state():
    db.reset()


# decode claude path tests


def test_decode_windows_path():
    # windows style encoded path with drive letter and double dash
    result = decode_claude_path("C--Users-adity-Desktop-coding-projects-talktome")
    assert result == "C:/Users/adity/Desktop/coding/projects/talktome"


def test_decode_simple_path():
    # path without a drive letter prefix
    result = decode_claude_path("home-user-projects-myapp")
    assert result == "home/user/projects/myapp"


def test_decode_short_path():
    # very short directory name should not crash
    result = decode_claude_path("ab")
    assert result == "ab"


def test_decode_single_char():
    # single character edge case
    result = decode_claude_path("x")
    assert result == "x"


def test_decode_empty_string():
    # empty string should return empty
    result = decode_claude_path("")
    assert result == ""


def test_decode_no_double_dash():
    # path that looks like a drive but lacks the double dash
    result = decode_claude_path("C-Users-something")
    assert result == "C/Users/something"


# read session meta tests


def test_read_session_meta_basic():
    # create a temp jsonl with a valid session record
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        record = {"type": "session", "cwd": "/home/user/project", "slug": "my-session"}
        f.write(json.dumps(record) + "\n")
        fpath = f.name
    try:
        meta = read_session_meta(fpath)
        assert meta["cwd"] == "/home/user/project"
        assert meta["slug"] == "my-session"
    finally:
        os.unlink(fpath)


def test_read_session_meta_skips_snapshot():
    # file starts with a snapshot record, should skip to the real one
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        snapshot = {"type": "file-history-snapshot", "files": []}
        real = {"type": "session", "cwd": "/real/path", "gitBranch": "main"}
        f.write(json.dumps(snapshot) + "\n")
        f.write(json.dumps(real) + "\n")
        fpath = f.name
    try:
        meta = read_session_meta(fpath)
        assert meta["cwd"] == "/real/path"
        assert meta["gitBranch"] == "main"
    finally:
        os.unlink(fpath)


def test_read_session_meta_skips_empty_lines():
    # file has empty lines and blank lines before the real record
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write("\n")
        f.write("   \n")
        f.write(json.dumps({"type": "session", "slug": "after-blanks"}) + "\n")
        fpath = f.name
    try:
        meta = read_session_meta(fpath)
        assert meta["slug"] == "after-blanks"
    finally:
        os.unlink(fpath)


def test_read_session_meta_invalid_json():
    # file has invalid json lines followed by a valid one
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write("not valid json\n")
        f.write("{broken\n")
        f.write(json.dumps({"type": "session", "slug": "valid"}) + "\n")
        fpath = f.name
    try:
        meta = read_session_meta(fpath)
        assert meta["slug"] == "valid"
    finally:
        os.unlink(fpath)


def test_read_session_meta_empty_file():
    # empty file should return an empty dict
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        fpath = f.name
    try:
        meta = read_session_meta(fpath)
        assert meta == {}
    finally:
        os.unlink(fpath)


def test_read_session_meta_missing_file():
    # nonexistent file should return an empty dict without raising
    meta = read_session_meta("/nonexistent/path/session.jsonl")
    assert meta == {}


# sessions endpoint tests


@pytest.fixture
def fake_projects(tmp_path, monkeypatch):
    # create a fake claude projects directory with some sessions
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()

    # create a project directory with two session files
    proj = projects_dir / "C--Users-test-myproject"
    proj.mkdir()

    session1 = proj / "abc123.jsonl"
    session1.write_text(
        json.dumps(
            {
                "type": "session",
                "cwd": "C:/Users/test/myproject",
                "slug": "fix-bug",
                "gitBranch": "main",
                "timestamp": "2025-01-01T00:00:00Z",
            }
        )
        + "\n"
    )

    session2 = proj / "def456.jsonl"
    session2.write_text(
        json.dumps(
            {
                "type": "session",
                "cwd": "C:/Users/test/myproject",
                "slug": "add-feature",
                "gitBranch": "dev",
                "timestamp": "2025-01-02T00:00:00Z",
            }
        )
        + "\n"
    )

    # create another project with one session
    proj2 = projects_dir / "home-user-other"
    proj2.mkdir()

    session3 = proj2 / "ghi789.jsonl"
    session3.write_text(
        json.dumps(
            {
                "type": "session",
                "cwd": "/home/user/other",
                "slug": "refactor",
                "gitBranch": "feature",
                "timestamp": "2025-01-03T00:00:00Z",
            }
        )
        + "\n"
    )

    # patch the projects directory constant
    monkeypatch.setattr("talktome.server.CLAUDE_PROJECTS_DIR", str(projects_dir))
    return projects_dir


@pytest.mark.asyncio
async def test_sessions_endpoint(fake_projects):
    # the sessions endpoint should return all discovered projects and sessions
    app = mcp.http_app(path="/mcp")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "projects" in data
        # should find both project directories
        assert len(data["projects"]) == 2


@pytest.mark.asyncio
async def test_sessions_project_metadata(fake_projects):
    # each project should have the correct name and session count
    app = mcp.http_app(path="/mcp")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/sessions")
        data = resp.json()
        projects = data["projects"]

        # find the myproject entry
        myproj = [p for p in projects if "myproject" in p["path"]]
        assert len(myproj) == 1
        assert myproj[0]["sessionCount"] == 2
        assert myproj[0]["name"] == "myproject"


@pytest.mark.asyncio
async def test_sessions_session_metadata(fake_projects):
    # session records should contain the right fields from the jsonl
    app = mcp.http_app(path="/mcp")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/sessions")
        data = resp.json()
        projects = data["projects"]

        # find the project and check its sessions
        myproj = [p for p in projects if "myproject" in p["path"]][0]
        sessions = myproj["sessions"]

        # sessions should have slug, branch, cwd fields
        slugs = {s["slug"] for s in sessions}
        assert "fix-bug" in slugs
        assert "add-feature" in slugs

        # each session should have an id matching the filename
        ids = {s["id"] for s in sessions}
        assert "abc123" in ids
        assert "def456" in ids


@pytest.mark.asyncio
async def test_sessions_agent_linking(fake_projects):
    # when a registered agent path matches a project, it should appear in the response
    registry.register("backend", "C:/Users/test/myproject")

    app = mcp.http_app(path="/mcp")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/sessions")
        data = resp.json()
        projects = data["projects"]

        myproj = [p for p in projects if "myproject" in p["path"]][0]
        assert myproj["agent"] == "backend"


@pytest.mark.asyncio
async def test_sessions_no_agent(fake_projects):
    # projects without a registered agent should have agent as none
    app = mcp.http_app(path="/mcp")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/sessions")
        data = resp.json()
        projects = data["projects"]

        # neither project has a registered agent
        for p in projects:
            assert p["agent"] is None


@pytest.mark.asyncio
async def test_sessions_empty_dir(tmp_path, monkeypatch):
    # an empty projects directory should return an empty list
    projects_dir = tmp_path / "empty_projects"
    projects_dir.mkdir()
    monkeypatch.setattr("talktome.server.CLAUDE_PROJECTS_DIR", str(projects_dir))

    app = mcp.http_app(path="/mcp")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/sessions")
        data = resp.json()
        assert data["projects"] == []


@pytest.mark.asyncio
async def test_sessions_missing_dir(tmp_path, monkeypatch):
    # a nonexistent projects directory should return an empty list
    monkeypatch.setattr("talktome.server.CLAUDE_PROJECTS_DIR", str(tmp_path / "nonexistent"))

    app = mcp.http_app(path="/mcp")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/sessions")
        data = resp.json()
        assert data["projects"] == []


@pytest.mark.asyncio
async def test_agents_endpoint_includes_session_id():
    # registering with session_id should expose it in the agents response
    registry.register("myagent", "/some/path")
    registry.update_metadata("myagent", {"session_id": "abc123"})

    app = mcp.http_app(path="/mcp")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/agents")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["session_id"] == "abc123"


@pytest.mark.asyncio
async def test_agents_endpoint_empty_session_id():
    # agent without session_id in metadata should return empty string
    registry.register("myagent", "/some/path")

    app = mcp.http_app(path="/mcp")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/agents")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["session_id"] == ""


@pytest.mark.asyncio
async def test_register_stores_session_id():
    # posting session_id to register should store it in metadata
    app = mcp.http_app(path="/mcp")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/register",
            json={
                "name": "myagent",
                "path": "/some/path",
                "session_id": "sess-xyz",
            },
        )
        assert resp.status_code == 200

        # verify it shows up in agents
        resp = await client.get("/agents")
        data = resp.json()
        assert data[0]["session_id"] == "sess-xyz"


@pytest.mark.asyncio
async def test_sessions_per_session_agent_marking(fake_projects):
    # register an agent with a specific session_id that matches one session
    registry.register("backend", "C:/Users/test/myproject")
    registry.update_metadata("backend", {"session_id": "abc123"})

    app = mcp.http_app(path="/mcp")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/sessions")
        data = resp.json()
        projects = data["projects"]

        myproj = [p for p in projects if "myproject" in p["path"]][0]
        sessions = myproj["sessions"]

        # only the session with matching id should have the agent field set
        abc = [s for s in sessions if s["id"] == "abc123"][0]
        assert abc["agent"] == "backend"

        # the other session should not have an agent
        defn = [s for s in sessions if s["id"] == "def456"][0]
        assert defn["agent"] == ""
