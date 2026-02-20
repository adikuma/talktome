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


def wait_for_down(timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            httpx.get(f"{BASE_URL}/health", timeout=1)
        except (
            httpx.ConnectError,
            httpx.ReadError,
            httpx.ConnectTimeout,
            httpx.RemoteProtocolError,
        ):
            return True
        time.sleep(0.3)
    return False


def kill_existing_server():
    # kill any process listening on port 3456 so we get a clean start
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(["netstat", "-ano"], text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                if ":3456" in line and "LISTENING" in line:
                    pid = line.strip().split()[-1]
                    subprocess.run(
                        ["taskkill", "/PID", pid, "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            wait_for_down(timeout=5)
        except (subprocess.CalledProcessError, OSError):
            pass
    else:
        try:
            out = subprocess.check_output(
                ["lsof", "-ti", ":3456"], text=True, stderr=subprocess.DEVNULL
            )
            for pid in out.strip().split():
                subprocess.run(["kill", "-9", pid], stderr=subprocess.DEVNULL)
            wait_for_down(timeout=5)
        except (subprocess.CalledProcessError, OSError):
            pass


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
    # wait until port is actually freed
    wait_for_down(timeout=5)


def wipe_db():
    for ext in ["", "-wal", "-shm"]:
        path = DB_PATH + ext
        if os.path.exists(path):
            os.remove(path)


def test_message_persistence_across_restart():
    kill_existing_server()
    wipe_db()
    proc = start_server()
    try:
        client = httpx.Client(base_url=BASE_URL, timeout=5)
        client.post("/register", json={"name": "persist-a", "path": "/pa"})
        client.post("/register", json={"name": "persist-b", "path": "/pb"})
        client.post(
            "/send",
            json={"sender": "persist-a", "peer": "persist-b", "message": "survive this"},
        )
        resp = client.get("/peek/persist-b")
        assert resp.json()["count"] == 1
        client.close()
    finally:
        stop_server(proc)

    # restart and check persistence
    proc2 = start_server()
    try:
        client2 = httpx.Client(base_url=BASE_URL, timeout=5)
        resp = client2.get("/peek/persist-b")
        data = resp.json()
        assert data["count"] == 1
        assert data["messages"][0]["message"] == "survive this"
        client2.close()
    finally:
        stop_server(proc2)


def test_dashboard_reconnect_overlay(page):
    kill_existing_server()
    wipe_db()
    proc = start_server()

    try:
        page.goto(BASE_URL)
        page.wait_for_selector(".logo")

        # verify connected
        expect(page.locator("#hd.on")).to_be_visible(timeout=5000)
        expect(page.locator("#reconnect.visible")).not_to_be_visible()

        # kill the server
        stop_server(proc)
        proc = None

        # overlay should appear
        expect(page.locator("#reconnect.visible")).to_be_visible(timeout=15000)

        # restart
        proc = start_server()

        # overlay should disappear and health dot should recover
        expect(page.locator("#reconnect.visible")).not_to_be_visible(timeout=15000)
        expect(page.locator("#hd.on")).to_be_visible(timeout=5000)

    finally:
        if proc:
            stop_server(proc)
