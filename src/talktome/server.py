from fastmcp import FastMCP

from talktome import registry

mcp = FastMCP("talktome")


@mcp.tool()
async def bridge_register(name: str, path: str) -> dict:
    """register a codebase with the bridge"""
    return registry.register(name, path)


@mcp.tool()
async def bridge_list_peers() -> list:
    """list all connected codebases"""
    return registry.list_all()


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=3456)
