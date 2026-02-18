import json
import os
import time
import urllib.error
import urllib.request

from fastmcp import FastMCP

BRIDGE_URL = os.environ.get("TALKTOME_URL", "http://127.0.0.1:3456")

proxy = FastMCP("talktome")


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
        "/send",
        method="POST",
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
        "/context",
        method="POST",
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
async def bridge_create_task(agent: str, description: str) -> dict:
    """create a task assigned to an agent"""
    return call_bridge(
        "/task",
        method="POST",
        data={"agent": agent, "description": description},
    )


@proxy.tool()
async def bridge_get_tasks(agent: str = "") -> list:
    """get tasks, optionally filtered by agent"""
    if agent:
        result = call_bridge(f"/tasks/{agent}")
    else:
        result = call_bridge("/tasks")
    if isinstance(result, list):
        return result
    return []


@proxy.tool()
async def bridge_update_task(task_id: str, status: str, result: str = "") -> dict:
    """update a task status (pending/running/done/failed) and optional result"""
    data = {"status": status}
    if result:
        data["result"] = result
    return call_bridge(f"/task/{task_id}", method="PATCH", data=data)


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
