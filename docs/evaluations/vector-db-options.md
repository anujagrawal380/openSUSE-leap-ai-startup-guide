# Vector DB Evaluation and Verdict

Status: Week 1 decision note

The assistant needs an embedded/offline vector store that can be packaged for openSUSE and used during first boot without running a separate database service.

## Verdict

Use **LanceDB as the target production vector store**, while keeping **ChromaDB as the PoC fallback until the LanceDB backend is implemented and tested**.

Reason: LanceDB best matches this project's distribution shape: embedded library, local filesystem database, Apache 2.0, no daemon, portable Lance/Arrow-style data layout, metadata filtering, full-text/hybrid search path, and Python/Rust ecosystem alignment. That is a better long-term fit for an RPM-shipped documentation index than a Python-heavy PoC database.

## Ranking

| Rank | Candidate | Verdict | Why |
|---:|---|---|---|
| 1 | LanceDB | Adopt after backend PoC | Best packaging/distribution fit: embedded OSS library, local path DB, Apache 2.0, metadata filtering, full-text/hybrid search, portable data format |
| 2 | ChromaDB | Keep as current fallback | Already implemented and supports metadata filtering, but packaging and Python dependency weight are less attractive |
| 3 | Qdrant Edge / local | Revisit if LanceDB fails | Strong engine and offline/embedded direction, but adds another retrieval stack and needs packaging verification |
| 4 | Milvus Lite | Do not choose for first version | Capable, but heavier than needed for a first-boot local assistant; better if future scale requires Milvus compatibility |
| 5 | FalconDB | Do not prioritize | Meeting note needs clarification; not clearly the best embedded vector/RAG store for this use case |
| 6 | Pinecone | Reject for default path | Strong managed vector DB, but cloud/network dependency conflicts with offline firstboot and RPM packaging |
| 7 | Weaviate / full Milvus | Reject for default path | Server/daemon operational model is too heavy for first boot and low-resource systems |

## Detailed Comparison

| Criterion | ChromaDB | LanceDB | Qdrant Edge/local | Milvus Lite |
|---|---|---|---|---|
| Offline after setup | Yes | Yes | Yes | Yes |
| Runs without daemon | Yes | Yes | Yes for Edge/local | Yes |
| Local filesystem persistence | Yes | Yes | Yes | Yes |
| Metadata filtering | Yes | Yes | Yes | Yes |
| Full-text/hybrid path | Yes | Yes | Yes | Yes |
| Prebuilt index portability | Acceptable, needs validation | Strong fit | Needs validation | Acceptable, needs validation |
| RPM packaging outlook | Medium risk | Best outlook | Medium risk | Medium/high risk |
| Low-RAM firstboot fit | Good | Good | Good | Medium |
| Existing project effort | Already done | New backend | New backend | New backend |
| Long-term maintainer confidence | Medium | High | Medium/high | Medium |

## Candidate Notes

### LanceDB

Choose this as the production target.

Evidence:

- LanceDB describes the OSS version as an embedded library with Python, TypeScript, and Rust clients.
- It connects to a local path and supports vector search plus metadata filtering, full-text search, and hybrid search.
- LanceDB is built around the open Lance format, which is useful for shipping or refreshing a prebuilt documentation index.
- Apache 2.0 licensing is clean for openSUSE packaging review.

Why it fits openSUSE:

- No system service or database daemon.
- A prebuilt index can live under `/usr/share/suse-assist/vectorstore` or be copied into `/var/lib/suse-assist`.
- Rust-backed implementation is more credible for distro packaging than a large pure-Python service stack.

Risk:

- Need to verify OBS availability or package `python-lancedb` and its native dependencies.
- Need to implement one backend adapter and compare query quality against current Chroma output.

### ChromaDB

Keep this until LanceDB is working.

Evidence:

- Chroma supports persistent/local usage and client-server mode.
- It has metadata filtering with equality, range, logical operators, inclusion operators, and array metadata.
- It is already integrated in this PoC.

Why it is not the final default:

- It is fine for prototype velocity, but the dependency stack is less attractive for a base distribution feature.
- Its packaging story needs more work than LanceDB's embedded-file model.

### Qdrant Edge / Local

Keep as a backup option.

Evidence:

- Qdrant documents Qdrant Edge as an embedded vector search engine for in-process, offline retrieval with no background service.
- Qdrant has mature search/filtering semantics.

Why it is not first:

- It is a second stack to evaluate deeply.
- It may be a strong future option, but LanceDB aligns more directly with prebuilt, file-oriented RAG indexes.

### Milvus Lite

Do not use for the first production version.

Evidence:

- Milvus Lite is imported into Python applications, persists to a local file, and supports vector CRUD, metadata filtering, sparse/dense search, multi-vector, and hybrid search.
- It targets laptops and edge devices.

Why it is not first:

- It brings the Milvus ecosystem into a use case that does not need Milvus-scale operations.
- It is likely heavier than LanceDB/Chroma for openSUSE firstboot onboarding.

### Pinecone

Reject for the default openSUSE assistant.

Evidence:

- Pinecone has strong managed/serverless vector search, metadata filtering, hybrid search, and namespace support.
- It is a good hosted RAG database when cloud operation is acceptable.

Why it does not fit this project:

- It is a managed cloud service, not an embedded/offline vector store.
- It cannot be shipped as the local RPM vector database.
- It requires network access and an API key, which conflicts with firstboot, air-gapped, and privacy-first goals.
- Query text and retrieved-document usage would leave the machine unless a separate hosted privacy design exists.

Verdict: mention Pinecone as a hosted-demo or future enterprise/cloud option only. Do not use it for the production local assistant.

## Implementation Decision

Use a backend interface, but implement only two backends now:

```python
class VectorStoreBackend:
    def ingest(self, chunks: list[DocumentChunk]) -> int: ...
    def retrieve(
        self,
        query: str,
        top_k: int,
        filters: dict | None = None,
    ) -> list[SearchResult]: ...
    def count(self) -> int: ...
```

Implementation order:

1. Keep existing `ChromaDB` path stable.
2. Add `LanceDB` backend behind `rag.backend: "lancedb"`.
3. Ingest the same openSUSE docs into both stores.
4. Compare top-k retrieval overlap and source quality on the benchmark query set.
5. If LanceDB matches or beats Chroma quality, make LanceDB the default and keep Chroma as a compatibility fallback.

## Sources

- LanceDB docs: https://docs.lancedb.com/
- LanceDB quickstart: https://docs.lancedb.com/quickstart
- LanceDB vector search: https://docs.lancedb.com/search/vector-search
- Chroma client-server mode: https://docs.trychroma.com/docs/run-chroma/client-server
- Chroma metadata filtering: https://docs.trychroma.com/docs/querying-collections/metadata-filtering
- Pinecone metadata filtering: https://docs.pinecone.io/guides/search/filter-by-metadata
- Pinecone serverless overview: https://www.pinecone.io/blog/serverless/
- Qdrant documentation / Edge overview: https://qdrant.tech/documentation/
- Milvus Lite docs: https://milvus.io/docs/milvus_lite.md
