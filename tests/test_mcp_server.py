"""Tests for the MCP server PoC (skipped when 'mcp' is not installed)."""

import asyncio

import pytest

pytest.importorskip("mcp")

from opensuse_ai.config import Config  # noqa: E402
from opensuse_ai.mcp_server import build_server  # noqa: E402


@pytest.fixture()
def server(tmp_path):
    cfg = Config()
    cfg.data_dir = str(tmp_path / "data")
    cfg.rag.persist_directory = str(tmp_path / "vectorstore")
    return build_server(cfg)


def test_tools_registered(server):
    """Both PoC tools should be exposed."""
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert names == {"get_system_context", "search_docs"}


def test_get_system_context_tool(server):
    """get_system_context should return a non-empty summary."""
    result = asyncio.run(server.call_tool("get_system_context", {}))
    text = result[0][0].text if isinstance(result, tuple) else result[0].text
    assert "Kernel:" in text
    assert "Package Manager:" in text


def test_search_docs_empty_index(server):
    """search_docs on an empty index should return the ingest hint."""
    result = asyncio.run(server.call_tool("search_docs", {"query": "zypper"}))
    text = result[0][0].text if isinstance(result, tuple) else result[0].text
    assert "index is empty" in text
