import uuid
from pathlib import Path

from fastmcp import FastMCP
from starlette.responses import HTMLResponse, JSONResponse

from talktome import db, queue, registry

mcp = FastMCP("talktome")


@mcp.tool()
async def bridge_register(name: str, path: str) -> dict:
    """register a codebase with the bridge"""
    db.log_activity("register", agent=name, path=path)
    return registry.register(name, path)


@mcp.tool()
async def bridge_list_peers() -> list:
    """list all connected codebases"""
    return registry.list_all()


@mcp.tool()
async def bridge_send_message(sender: str, peer: str, message: str) -> str:
    """send an async message to a peer codebase's mailbox"""
    if not registry.is_registered(peer):
        return f"peer '{peer}' not found"
    queue.send(sender, peer, message)
    db.log_activity("message", sender=sender, peer=peer, content=message)
    return f"message sent to {peer}"


@mcp.tool()
async def bridge_read_mailbox(name: str) -> list[dict]:
    """read and drain all incoming messages for this agent"""
    return queue.read(name)


@mcp.tool()
async def bridge_share_context(owner: str, key: str, value: str) -> str:
    """push a piece of context that other peers can read"""
    db.set_context(owner, key, value)
    return f"context '{key}' stored for {owner}"


@mcp.tool()
async def bridge_get_context(owner: str, key: str) -> str:
    """pull a piece of context from a peer"""
    value = db.get_context(owner, key)
    if value is None:
        return f"no context '{key}' found for {owner}"
    return value


@mcp.tool()
async def bridge_create_task(agent: str, description: str) -> dict:
    """create a task assigned to an agent"""
    task_id = uuid.uuid4().hex[:8]
    task = db.create_task(task_id, agent, description)
    db.log_activity("task_created", agent=agent, task_id=task_id, description=description)
    return task


@mcp.tool()
async def bridge_get_tasks(agent: str = "") -> list:
    """get tasks, optionally filtered by agent"""
    if agent:
        return db.get_agent_tasks(agent)
    return db.get_tasks()


@mcp.tool()
async def bridge_update_task(task_id: str, status: str, result: str = "") -> dict:
    """update a task's status (pending/running/done/failed) and optional result"""
    task = db.update_task(task_id, status=status, result=result or None)
    if task is None:
        return {"error": f"task '{task_id}' not found"}
    db.log_activity("task_updated", task_id=task_id, status=status)
    return task


@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    return JSONResponse({"status": "ok"})


@mcp.custom_route("/peek/{name}", methods=["GET"])
async def peek(request):
    name = request.path_params["name"]
    messages = queue.peek(name)
    return JSONResponse({"count": len(messages), "messages": messages})


@mcp.custom_route("/register", methods=["POST"])
async def register_rest(request):
    body = await request.json()
    name = body.get("name", "")
    path = body.get("path", "")
    if not name:
        return JSONResponse({"error": "name required"}, status_code=400)
    db.log_activity("register", agent=name, path=path)
    entry = registry.register(name, path)
    return JSONResponse(entry)


@mcp.custom_route("/agents", methods=["GET"])
async def agents(request):
    names = registry.list_all()
    result = []
    for name in names:
        entry = registry.get(name)
        result.append(
            {
                "name": name,
                "path": entry["path"] if entry else "",
                "status": entry["status"] if entry else "unknown",
                "mailbox_count": queue.count(name),
            }
        )
    return JSONResponse(result)


@mcp.custom_route("/activity", methods=["GET"])
async def activity(request):
    return JSONResponse(db.get_activity())


@mcp.custom_route("/", methods=["GET"])
async def dashboard(request):
    html_path = Path(__file__).parent / "dashboard.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@mcp.custom_route("/send", methods=["POST"])
async def send_rest(request):
    body = await request.json()
    sender = body.get("sender", "")
    peer = body.get("peer", "")
    message = body.get("message", "")
    if not peer:
        return JSONResponse({"error": "peer required"}, status_code=400)
    if not registry.is_registered(peer):
        return JSONResponse({"result": f"peer '{peer}' not found"})
    queue.send(sender, peer, message)
    db.log_activity("message", sender=sender, peer=peer, content=message)
    return JSONResponse({"result": f"message sent to {peer}"})


@mcp.custom_route("/read/{name}", methods=["GET"])
async def read_rest(request):
    name = request.path_params["name"]
    messages = queue.read(name)
    return JSONResponse(messages)


@mcp.custom_route("/context", methods=["POST"])
async def context_store_rest(request):
    body = await request.json()
    owner = body.get("owner", "")
    key = body.get("key", "")
    value = body.get("value", "")
    db.set_context(owner, key, value)
    return JSONResponse({"result": f"context '{key}' stored for {owner}"})


@mcp.custom_route("/context/{owner}/{key}", methods=["GET"])
async def context_get_rest(request):
    owner = request.path_params["owner"]
    key = request.path_params["key"]
    value = db.get_context(owner, key)
    if value is None:
        return JSONResponse({"error": f"no context '{key}' found for {owner}"})
    return JSONResponse({"value": value})


@mcp.custom_route("/task", methods=["POST"])
async def task_create_rest(request):
    body = await request.json()
    agent = body.get("agent", "")
    description = body.get("description", "")
    if not agent or not description:
        return JSONResponse({"error": "agent and description required"}, status_code=400)
    task_id = uuid.uuid4().hex[:8]
    task = db.create_task(task_id, agent, description)
    db.log_activity("task_created", agent=agent, task_id=task_id, description=description)
    return JSONResponse(task)


@mcp.custom_route("/tasks", methods=["GET"])
async def tasks_list_rest(request):
    return JSONResponse(db.get_tasks())


@mcp.custom_route("/tasks/{agent}", methods=["GET"])
async def tasks_agent_rest(request):
    agent = request.path_params["agent"]
    return JSONResponse(db.get_agent_tasks(agent))


@mcp.custom_route("/task/{task_id}", methods=["PATCH"])
async def task_update_rest(request):
    task_id = request.path_params["task_id"]
    body = await request.json()
    status = body.get("status")
    result = body.get("result")
    task = db.update_task(task_id, status=status, result=result)
    if task is None:
        return JSONResponse({"error": f"task '{task_id}' not found"}, status_code=404)
    db.log_activity("task_updated", task_id=task_id, status=status)
    return JSONResponse(task)


@mcp.custom_route("/tasks/{agent}/pending", methods=["GET"])
async def tasks_pending_rest(request):
    agent = request.path_params["agent"]
    return JSONResponse(db.get_pending_tasks(agent))


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=3456)
