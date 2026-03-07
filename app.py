"""
HuggingFace Spaces entry point.

This file is the Gradio app entry point expected by HuggingFace Spaces.
It initialises the assistant in demo mode and launches the web UI.
"""

import logging
import os

from opensuse_ai.config import Config
from opensuse_ai.web_ui import build_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# On HF Spaces, ingest docs at startup if vector store is empty
config = Config.from_yaml("config.yaml")

# HF Spaces: use API mode (no llama-cpp-python needed) and disable GPU offloading
config.model.inference_mode = "api"
config.model.n_gpu_layers = 0


def _ensure_data():
    """Scrape docs and build vector store if not already present."""
    from pathlib import Path

    from opensuse_ai.rag import RAGPipeline

    rag = RAGPipeline(config)
    if rag.is_populated:
        logging.info("Vector store already populated, skipping ingest.")
        return

    logging.info("First run — ingesting openSUSE documentation...")
    from opensuse_ai.scraper import scrape_all_sources

    # Limit pages on Spaces to keep startup fast
    for src in config.doc_sources:
        src.max_pages = 5

    data_dir = Path(config.data_dir)
    pages = scrape_all_sources(config.doc_sources, data_dir)

    if pages:
        rag.ingest(pages)
        logging.info("Ingestion complete: %d pages indexed.", len(pages))
    else:
        logging.warning("No pages scraped — assistant will run without RAG context.")


_ensure_data()

app = build_app(config, demo_mode=True)

if __name__ == "__main__":
    app.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", 7860)),
    )
