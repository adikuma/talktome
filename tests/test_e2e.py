import os
import signal
import subprocess
import sys
import time

import httpx
import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

BASE_URL = "http://127.0.0.1:3456"
DB_PATH = os.path.join(os.path.expanduser("~"), ".talktome", "bridge.db")


def wait_for_health(timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{BASE_URL}/health", timeout=2)
            if resp.status_code == 200:
                return True
        except httpx.ConnectError:
            pass
        time.sleep(0.5)
    return False


def start_server():
    proc = subprocess.Popen(
        [sys.executable, "-m", "talktome"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )
    if not wait_for_health():
        proc.kill()
        raise RuntimeError("talktome server did not start")
    return proc


def stop_server(proc):
    if sys.platform == "win32":
        proc.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def wipe_db():
    for ext in ["", "-wal", "-shm"]:
        path = DB_PATH + ext
        if os.path.exists(path):
            os.remove(path)


# ── fixtures ──


@pytest.fixture(scope="module")
def server():
    wipe_db()
    proc = start_server()
    yield proc
    stop_server(proc)


@pytest.fixture
def api(server):
    with httpx.Client(base_url=BASE_URL, timeout=5) as client:
        yield client


# ── api tests ──


def test_health(api):
    resp = api.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_register_agents(api):
    api.post("/register", json={"name": "e2e-alpha", "path": "/project-alpha"})
    api.post("/register", json={"name": "e2e-beta", "path": "/project-beta"})
    resp = api.get("/agents")
    names = [a["name"] for a in resp.json()]
    assert "e2e-alpha" in names
    assert "e2e-beta" in names


def test_messaging_roundtrip(api):
    api.post("/register", json={"name": "e2e-sender", "path": "/s"})
    api.post("/register", json={"name": "e2e-receiver", "path": "/r"})
    api.post(
        "/send",
        json={"sender": "e2e-sender", "peer": "e2e-receiver", "message": "ping"},
    )

    # peek should show message without draining
    resp = api.get("/peek/e2e-receiver")
    data = resp.json()
    assert data["count"] == 1
    assert data["messages"][0]["message"] == "ping"

    # read should drain
    resp = api.get("/read/e2e-receiver")
    assert len(resp.json()) == 1

    # peek should now be empty
    resp = api.get("/peek/e2e-receiver")
    assert resp.json()["count"] == 0


def test_task_lifecycle(api):
    api.post("/register", json={"name": "e2e-worker", "path": "/w"})
    resp = api.post(
        "/task",
        json={"agent": "e2e-worker", "description": "do the thing"},
    )
    task_id = resp.json()["id"]

    # check pending
    resp = api.get("/tasks/e2e-worker")
    tasks = resp.json()
    assert any(t["id"] == task_id and t["status"] == "pending" for t in tasks)

    # update to running
    api.patch(f"/task/{task_id}", json={"status": "running"})
    resp = api.get("/tasks/e2e-worker")
    tasks = resp.json()
    assert any(t["id"] == task_id and t["status"] == "running" for t in tasks)

    # update to done with result
    api.patch(f"/task/{task_id}", json={"status": "done", "result": "did it"})
    resp = api.get("/tasks/e2e-worker")
    tasks = resp.json()
    done = [t for t in tasks if t["id"] == task_id][0]
    assert done["status"] == "done"
    assert done["result"] == "did it"


def test_deregistration(api):
    api.post("/register", json={"name": "e2e-leaving", "path": "/l"})
    resp = api.get("/agents")
    agent = [a for a in resp.json() if a["name"] == "e2e-leaving"][0]
    assert agent["status"] == "active"

    api.post("/deregister", json={"name": "e2e-leaving"})
    resp = api.get("/agents")
    agent = [a for a in resp.json() if a["name"] == "e2e-leaving"][0]
    assert agent["status"] == "inactive"


# ── playwright dashboard tests ──


@pytest.fixture
def dashboard(page, server):
    page.goto(BASE_URL)
    page.wait_for_selector(".logo")
    return page


def test_dashboard_loads(dashboard):
    expect(dashboard.locator(".logo")).to_have_text("talktome")


def test_dashboard_health_dot(dashboard):
    expect(dashboard.locator("#hd.on")).to_be_visible(timeout=5000)


def test_dashboard_shows_agents(dashboard, api):
    api.post("/register", json={"name": "ui-agent-x", "path": "/px"})

    # wait for agent to appear in sidebar
    expect(dashboard.locator(".agent-name", has_text="ui-agent-x")).to_be_visible(timeout=8000)


def test_dashboard_shows_messages(dashboard, api):
    api.post("/register", json={"name": "msg-from", "path": "/mf"})
    api.post("/register", json={"name": "msg-to", "path": "/mt"})
    api.post(
        "/send",
        json={"sender": "msg-from", "peer": "msg-to", "message": "hello dashboard"},
    )

    # wait for agent to appear then click it
    expect(dashboard.locator(".agent-name", has_text="msg-to")).to_be_visible(timeout=8000)
    dashboard.locator(".agent-name", has_text="msg-to").click()

    # wait for message to render
    expect(dashboard.locator(".msg-body", has_text="hello dashboard")).to_be_visible(timeout=8000)


def test_dashboard_send_task(dashboard, api):
    api.post("/register", json={"name": "task-target", "path": "/tt"})

    # wait for agent to appear in the dropdown
    expect(dashboard.locator(".agent-name", has_text="task-target")).to_be_visible(timeout=8000)

    # select agent in dropdown
    dashboard.locator("#cmd-agent").select_option("task-target")

    # type and send a task
    dashboard.locator("#cmd-input").fill("e2e test task")
    dashboard.locator("#cmd-send").click()

    # verify the task shows up
    expect(dashboard.locator(".task-desc", has_text="e2e test task")).to_be_visible(timeout=8000)
