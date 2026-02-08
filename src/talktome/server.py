from fastmcp import FastMCP

from talktome import queue, registry

# shared context store — keyed by (owner, key)
context_store: dict[tuple[str, str], str] = {}

mcp = FastMCP("talktome")


@mcp.tool()
async def bridge_register(name: str, path: str) -> dict:
    """register a codebase with the bridge"""
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



if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=3456)
