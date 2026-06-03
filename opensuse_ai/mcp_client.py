"""
MCP client PoC: the assistant consuming tools from external MCP servers.

Counterpart to ``mcp_server.py``: where the server PoC lets other agents use
*our* capabilities, this client lets the onboarding assistant call tools
hosted by *any* MCP server (over stdio). Demonstrated end-to-end by pointing
it at our own server:

    suse-assist mcp-tools list
    suse-assist mcp-tools call get_system_context
    suse-assist mcp-tools call search_docs --args '{"query": "snapper rollback"}'

Requires the optional dependency:  pip install 'opensuse-leap-ai-guide[mcp]'
"""

import asyncio
import logging
import os
import shlex

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The 'mcp' package is required for the MCP client. "
        "Install it with: pip install mcp"
    ) from exc

logger = logging.getLogger(__name__)

# Default server: our own MCP server PoC, spawned as a subprocess.
DEFAULT_SERVER_COMMAND = "suse-assist mcp"


def _server_params(command: str) -> StdioServerParameters:
    # The MCP SDK spawns servers with a minimal environment by default,
    # which would strip SUSE_AI_HOST_ROOT / HF_HUB_OFFLINE and break
    # host-aware detection and offline mode. Inherit our environment.
    parts = shlex.split(command)
    return StdioServerParameters(
        command=parts[0], args=parts[1:], env=dict(os.environ)
    )


async def _with_session(command: str, fn):
    """Open a stdio session against *command* and run *fn(session)*."""
    async with stdio_client(_server_params(command)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


def list_tools(command: str = DEFAULT_SERVER_COMMAND) -> list[dict]:
    """List the tools an MCP server exposes (name, description, schema)."""

    async def _list(session: ClientSession):
        result = await session.list_tools()
        return [
            {
                "name": t.name,
                "description": (t.description or "").strip(),
                "input_schema": t.inputSchema,
            }
            for t in result.tools
        ]

    return asyncio.run(_with_session(command, _list))


def call_tool(
    name: str,
    arguments: dict | None = None,
    command: str = DEFAULT_SERVER_COMMAND,
) -> str:
    """Call a tool on an MCP server and return its text output."""

    async def _call(session: ClientSession):
        result = await session.call_tool(name, arguments or {})
        texts = [c.text for c in result.content if getattr(c, "text", None)]
        return "\n".join(texts)

    return asyncio.run(_with_session(command, _call))
