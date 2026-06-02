"""One-off local ingest: scrape configured doc sources and build the LanceDB
vector store on a machine with internet, for shipping to an offline VM.

Run with the .venv-ingest interpreter from the repo root:
    .venv-ingest/bin/python scripts/local_ingest.py
"""

import shutil
from pathlib import Path

from opensuse_ai.config import Config
from opensuse_ai.rag import RAGPipeline
from opensuse_ai.scraper import scrape_all_sources

cfg = Config.from_yaml("config.yaml")
print(f"backend={cfg.rag.backend} data_dir={cfg.data_dir} sources={len(cfg.doc_sources)}")

# Clean rebuild: LanceDB add_documents() appends, so drop any prior store first.
store = Path(cfg.rag.persist_directory)
if store.exists():
    print(f"removing existing vector store at {store}")
    shutil.rmtree(store)

pages = scrape_all_sources(cfg.doc_sources, Path(cfg.data_dir))
by_source: dict[str, int] = {}
for p in pages:
    host = p.url.split("/")[2] if "://" in p.url else p.url
    tag = "release-notes" if "release-notes" in p.url else "manual"
    by_source[tag] = by_source.get(tag, 0) + 1
print(f"scraped {len(pages)} pages: {by_source}")

rag = RAGPipeline(cfg)
n = rag.ingest(pages)
print(f"indexed {n} chunks into {cfg.rag.persist_directory}")
