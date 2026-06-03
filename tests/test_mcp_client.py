"""End-to-end test: MCP client against our own MCP server (stdio)."""

import sys

import pytest

pytest.importorskip("mcp")

from opensuse_ai.mcp_client import call_tool, list_tools  # noqa: E402

# Spawn the server with the same interpreter running the tests so the test
# does not depend on a 'suse-assist' entrypoint being on PATH.
SERVER_COMMAND = f"{sys.executable} -m opensuse_ai.cli mcp"


def test_client_lists_server_tools():
    """The client should discover both tools from a spawned server."""
    tools = list_tools(SERVER_COMMAND)
    names = {t["name"] for t in tools}
    assert names == {"get_system_context", "search_docs"}


def test_client_calls_system_context_tool():
    """Calling get_system_context through MCP should return the summary."""
    result = call_tool("get_system_context", command=SERVER_COMMAND)
    assert "Kernel:" in result
    assert "Package Manager:" in result
