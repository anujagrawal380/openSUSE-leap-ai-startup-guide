"""
Vector store backends for the openSUSE AI assistant.

Provides a pluggable abstraction over different vector databases
(ChromaDB, LanceDB) used by the RAG pipeline.
"""

from opensuse_ai.vectorstore.base import VectorStoreBackend

__all__ = ["VectorStoreBackend"]
