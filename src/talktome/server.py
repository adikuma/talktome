import time
from pathlib import Path

from fastmcp import FastMCP
from starlette.responses import HTMLResponse, JSONResponse

from talktome import queue, registry

# shared context store — keyed by (owner, key)
context_store: dict[tuple[str, str], str] = {}

# activity log — recent events for the dashboard
activity_log: list[dict] = []

mcp = FastMCP("talktome")


def log_activity(event: str, **kwargs: str) -> None:
    activity_log.append({"event": event, "timestamp": time.time(), **kwargs})
    # keep only the last 100 events
    if len(activity_log) > 100:
        activity_log.pop(0)


@mcp.tool()
async def bridge_register(name: str, path: str) -> dict:
    """register a codebase with the bridge"""
    log_activity("register", agent=name, path=path)
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
    log_activity("message", sender=sender, peer=peer, content=message)
    return f"message sent to {peer}"


@mcp.tool()
async def bridge_read_mailbox(name: str) -> list[dict]:
    """read and drain all incoming messages for this agent"""
    return queue.read(name)


@mcp.tool()
async def bridge_share_context(owner: str, key: str, value: str) -> str:
    """push a piece of context that other peers can read"""
    context_store[(owner, key)] = value
    return f"context '{key}' stored for {owner}"


@mcp.tool()
async def bridge_get_context(owner: str, key: str) -> str:
    """pull a piece of context from a peer"""
    value = context_store.get((owner, key))
    if value is None:
        return f"no context '{key}' found for {owner}"
    return value


@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    return JSONResponse({"status": "ok"})


@mcp.custom_route("/peek/{name}", methods=["GET"])
async def peek(request):
    name = request.path_params["name"]
    messages = queue.peek(name)
    return JSONResponse({"count": len(messages), "messages": messages})


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
    return JSONResponse(activity_log)


@mcp.custom_route("/", methods=["GET"])
async def dashboard(request):
    html_path = Path(__file__).parent / "dashboard.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=3456)
