"""
MCP (Model Context Protocol) server exposing the assistant's capabilities.

Implements the GSoC proposal's MCP integration milestone: any MCP-capable
client (Claude Desktop, other LLM agents, IDEs) can use the openSUSE
system context and documentation search as tools, instead of going
through our bundled chat UI.

Run with:  suse-assist mcp        (stdio transport)

Requires the optional dependency:  pip install 'opensuse-leap-ai-guide[mcp]'
"""

import logging

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The 'mcp' package is required for the MCP server. "
        "Install it with: pip install mcp"
    ) from exc

from opensuse_ai.config import Config
from opensuse_ai.rag import RAGPipeline
from opensuse_ai.system_context import detect_system_context

logger = logging.getLogger(__name__)


def build_server(config: Config) -> FastMCP:
    """Create the FastMCP server with system-context and doc-search tools."""
    mcp = FastMCP(
        "opensuse-onboarding",
        instructions=(
            "Tools for onboarding users to openSUSE Leap: live system state "
            "detection and semantic search over official openSUSE documentation."
        ),
    )

    # RAG pipeline is loaded lazily on first search so that a client that only
    # wants system context doesn't pay the embedding-model startup cost.
    state: dict = {"rag": None}

    def _rag() -> RAGPipeline:
        if state["rag"] is None:
            state["rag"] = RAGPipeline(config)
        return state["rag"]

    @mcp.tool()
    def get_system_context() -> str:
        """
        Detect the current openSUSE system state: distribution and version,
        kernel, desktop environment, package manager, root filesystem and
        Snapper snapshot availability, GPU, locale, network and firewall
        state, memory and disk usage.
        """
        return detect_system_context().summary()

    @mcp.tool()
    def search_docs(query: str, top_k: int = 5) -> str:
        """
        Semantic search over the indexed openSUSE documentation (Startup
        Guide, Reference, Leap 16.0 Release Notes). Returns the most
        relevant passages with source URLs.

        Args:
            query: Natural-language question or keywords.
            top_k: Number of passages to return (1-10).
        """
        top_k = max(1, min(int(top_k), 10))
        pipeline = _rag()
        if not pipeline.is_populated:
            return (
                "The documentation index is empty. "
                "Run 'suse-assist ingest' first to build it."
            )
        results = pipeline.retrieve(query, top_k=top_k)
        return pipeline.format_context(results)

    return mcp


def serve(config: Config) -> None:
    """Run the MCP server over stdio (blocks until the client disconnects)."""
    build_server(config).run(transport="stdio")
