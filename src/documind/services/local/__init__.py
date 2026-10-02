"""Local, offline-first service implementations.

These modules provide drop-in replacements for the Azure-based services
so DocuMind can run on a developer laptop with no cloud dependencies:

- ``sqlite_store``      — pipeline state / metadata (replaces Cosmos).
- ``chroma_search``     — vector + text search (replaces Cosmos vector).
- ``filesystem_blob``   — raw/processed file storage (replaces Blob).
- ``local_extractor``   — PDF/DOCX/XLSX/TXT parsing (replaces DI).
- ``ollama_llm``        — Ollama LLM + sentence-transformers embeddings.

All classes duck-type the public interface of their Azure counterpart so
the agents, orchestrator, and API endpoints require no changes.

Selection is driven by ``documind.services.factory``; do not import these
modules directly from application code.
"""
