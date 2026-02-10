import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

from fastmcp import FastMCP

BRIDGE_URL = os.environ.get("TALKTOME_URL", "http://127.0.0.1:3456")
TALKTOME_DIR = os.environ.get(
    "TALKTOME_DIR",
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)

proxy = FastMCP("talktome")


def is_bridge_running():
    try:
        req = urllib.request.Request(f"{BRIDGE_URL}/health")
        resp = urllib.request.urlopen(req, timeout=3)
        return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def start_bridge():
    # start the http bridge server in the background
    if sys.platform == "win32":
        subprocess.Popen(
            ["uv", "run", "--directory", TALKTOME_DIR, "python", "-m", "talktome"],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.Popen(
            ["uv", "run", "--directory", TALKTOME_DIR, "python", "-m", "talktome"],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    for _ in range(15):
        time.sleep(0.5)
        if is_bridge_running():
            return True
    return False


def ensure_bridge():
    if not is_bridge_running():
        return start_bridge()
    return True


def call_bridge(endpoint, method="GET", data=None):
    try:
        if data is not None:
            payload = json.dumps(data).encode()
            req = urllib.request.Request(
                f"{BRIDGE_URL}{endpoint}",
                data=payload,
                headers={"Content-Type": "application/json"},
                method=method,
            )
        else:
            req = urllib.request.Request(f"{BRIDGE_URL}{endpoint}", method=method)
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except (urllib.error.URLError, OSError) as e:
        return {"error": str(e)}


@proxy.tool()
async def bridge_register(name: str, path: str) -> dict:
    """register a codebase with the bridge"""
    return call_bridge("/register", method="POST", data={"name": name, "path": path})


@proxy.tool()
async def bridge_list_peers() -> list:
    """list all connected codebases"""
    result = call_bridge("/agents")
    if isinstance(result, list):
        return [a["name"] for a in result]
    return []


@proxy.tool()
async def bridge_send_message(sender: str, peer: str, message: str) -> str:
    """send an async message to a peer codebase's mailbox"""
    result = call_bridge(
        "/send", method="POST",
        data={"sender": sender, "peer": peer, "message": message},
    )
    return result.get("result", str(result))


@proxy.tool()
async def bridge_read_mailbox(name: str) -> list[dict]:
    """read and drain all incoming messages for this agent"""
    result = call_bridge(f"/read/{name}")
    if isinstance(result, list):
        return result
    return []


@proxy.tool()
async def bridge_share_context(owner: str, key: str, value: str) -> str:
    """push a piece of context that other peers can read"""
    result = call_bridge(
        "/context", method="POST",
        data={"owner": owner, "key": key, "value": value},
    )
    return result.get("result", str(result))


@proxy.tool()
async def bridge_get_context(owner: str, key: str) -> str:
    """pull a piece of context from a peer"""
    result = call_bridge(f"/context/{owner}/{key}")
    if "value" in result:
        return result["value"]
    return result.get("error", str(result))


@proxy.tool()
async def bridge_wait_for_reply(name: str, timeout: int = 30) -> list[dict]:
    """wait for messages to arrive in this agent's mailbox, polling every 2s"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = call_bridge(f"/peek/{name}")
        if isinstance(result, dict) and result.get("count", 0) > 0:
            return call_bridge(f"/read/{name}")
        time.sleep(2)
    return []


if __name__ == "__main__":
    ensure_bridge()
    proxy.run()
