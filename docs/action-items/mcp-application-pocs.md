# MCP Application PoCs

Status: proposed for Week 1 validation

This document translates the meeting action item "Explore practical MCP application PoCs" into small demos that can be shown to mentors before committing to production integration.

## Why MCP Matters Here

The assistant already has three useful capability boundaries:

- system context detection in `opensuse_ai/system_context.py`
- documentation retrieval in `opensuse_ai/rag.py`
- guided onboarding flows in `opensuse_ai/assistant.py`

MCP can expose those capabilities to external clients without turning the assistant itself into a monolithic UI. The production assistant can remain a CLI/web/systemd service, while MCP becomes an optional integration layer for tools that support MCP clients.

Reference:

- MCP architecture overview: https://modelcontextprotocol.io/docs/learn
- MCP example servers: https://modelcontextprotocol.io/examples

## PoC 1: System Context MCP Server

Goal: expose safe, read-only openSUSE system facts as MCP tools/resources.

Candidate capabilities:

- `get_system_context`: return distro, version, kernel, desktop environment, failed services summary, memory, disk, and update status.
- `get_onboarding_recommendations`: return suggested onboarding topics based on detected context.

Demo flow:

```bash
suse-assist mcp system-context
```

Then from an MCP client:

```text
What should I configure first on this openSUSE machine?
```

Acceptance criteria:

- The server does not require root.
- The server is read-only.
- No secrets, tokens, environment dumps, full logs, or full service output are exposed.
- Failed service output is summarized, not streamed raw.

Security notes:

- Keep this server local-only.
- Do not expose arbitrary shell execution.
- Treat all MCP client prompts as untrusted.

## PoC 2: Documentation RAG MCP Server

Goal: expose the local openSUSE documentation index as MCP context.

Candidate capabilities:

- `search_opensuse_docs(query, source_type?)`: return top matching chunks with title, URL, and source type.
- `get_doc_sources`: return indexed documentation collections and last ingestion timestamp.

Demo flow:

```bash
suse-assist ingest --max-pages 20
suse-assist mcp docs
```

Then from an MCP client:

```text
Use official openSUSE docs to explain how zypper repositories work.
```

Acceptance criteria:

- Retrieval works fully offline after ingestion.
- Returned chunks include source metadata.
- The MCP output remains citations-first and avoids unsupported claims.
- Source filtering can prioritize official docs over wiki/community pages.

## PoC 3: Onboarding Session MCP Server

Goal: expose structured onboarding flows as prompts/tools for MCP-capable clients.

Candidate capabilities:

- `list_onboarding_topics`
- `start_onboarding_topic(topic)`
- `ask_suse_assist(question, include_system_context=true)`

Demo flow:

```bash
suse-assist mcp onboarding
```

Then from an MCP client:

```text
Start the Snapper rollback onboarding flow and adapt it to my machine.
```

Acceptance criteria:

- The tool uses the same assistant engine as CLI/web.
- It preserves the same local/offline privacy model when configured for local inference.
- It applies the same prompt-injection constraints planned for normal chat.

## Recommendation

Start with PoC 1 and PoC 2. They are read-only, easy to review, and directly reuse existing code. PoC 3 is useful after model routing and prompt-injection handling are in place.

## Week 1 Output

- Add an `mcp/` prototype package or `opensuse_ai/mcp_server.py`.
- Demo system context retrieval through an MCP client.
- Demo documentation search through an MCP client.
- Document security boundaries before any write/action tools are considered.
