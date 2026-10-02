"""Application settings loaded from environment variables.

Uses pydantic-settings so every value can be overridden via env vars or a
.env file.  ``load_dotenv(override=False)`` is called so that runtime env
vars (e.g. from Container Apps) always take precedence over the .env file.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration — one place for all connection details."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Runtime env vars beat .env values (important for Container Apps)
        env_nested_delimiter="__",
        extra="ignore",
    )

    # ---- Backend selector ----
    # "local": run fully offline (Chroma + SQLite + Ollama + filesystem).
    # "azure": use Cosmos DB + Azure OpenAI + Blob Storage + Document Intelligence.
    backend: Literal["azure", "local"] = Field(
        "local", description="Which service backend to use for storage, search, LLM, and extraction."
    )

    # ---- Auth ----
    # "none" is the safe default for local dev; "api_key" or "entra_id" for Azure deployments.
    auth_mode: Literal["none", "api_key", "entra_id"] = Field(
        "none", description="Authentication mode for the API."
    )

    # ---- Azure AI Foundry / OpenAI ----
    foundry_project_endpoint: str = Field(
        "", description="Microsoft Foundry project endpoint URL."
    )
    foundry_model_deployment: str = Field(
        "gpt-4o", description="Model deployment name in Foundry."
    )
    azure_openai_endpoint: str = Field("", description="Azure OpenAI endpoint (fallback).")

    # ---- Document Intelligence ----
    azure_doc_intelligence_endpoint: str = Field("")
    azure_doc_intelligence_key: str = Field("", description="Optional — prefer managed identity.")

    # ---- AI Search ----
    azure_search_endpoint: str = Field("")
    azure_search_key: str = Field("", description="Optional — prefer managed identity.")
    azure_search_index_name: str = Field("documind-index")

    # ---- Blob Storage ----
    azure_storage_connection_string: str = Field("")
    azure_storage_account_name: str = Field("")
    azure_storage_container_raw: str = Field("raw-documents")
    azure_storage_container_processed: str = Field("processed")

    # ---- Cosmos DB ----
    azure_cosmos_endpoint: str = Field("")
    azure_cosmos_key: str = Field("", description="Optional — prefer managed identity.")
    azure_cosmos_database: str = Field("documind")
    azure_cosmos_container: str = Field("documents")

    # ---- Key Vault ----
    azure_keyvault_url: str = Field("")

    # ---- Monitoring ----
    applicationinsights_connection_string: str = Field("")

    # ---- Pipeline / Chunker ----
    chunker_max_tokens: int = Field(8000, description="Max tokens per chunk for LLM analysis.")
    chunker_overlap_tokens: int = Field(200, description="Overlap tokens between consecutive chunks.")

    # ---- Embedding ----
    embedding_model: str = Field("text-embedding-3-small", description="Embedding model deployment name.")
    embedding_dimensions: int = Field(1536, description="Embedding vector dimensions (must match model).")

    # ---- Cosmos DB Vector Search ----
    cosmos_search_container: str = Field("search_index", description="Cosmos DB container for vector search index.")

    # ---- LLM Parameters ----
    llm_temperature: float = Field(0.2, ge=0.0, le=2.0, description="Temperature for LLM completions.")

    # ---- OpenAI (used by analysis tools & MCP) ----
    azure_openai_key: str = Field("", description="Azure OpenAI API key.")
    azure_openai_api_version: str = Field("2024-12-01-preview", description="Azure OpenAI API version.")
    azure_openai_deployment: str = Field("gpt-4o", description="Azure OpenAI deployment name.")

    # ---- Local backend: ChromaDB ----
    chroma_path: str = Field("./data/chroma", description="ChromaDB persistence directory.")
    chroma_collection: str = Field("documind", description="ChromaDB collection name.")

    # ---- Local backend: SQLite (metadata / pipeline state) ----
    sqlite_path: str = Field("./data/documind.sqlite", description="SQLite file for document records.")

    # ---- Local backend: filesystem blob store ----
    local_blob_dir: str = Field("./data/blobs", description="Root directory for locally stored uploads.")

    # ---- Local backend: Ollama (LLM) ----
    ollama_base_url: str = Field("http://localhost:11434", description="Base URL of the local Ollama server.")
    ollama_model: str = Field("llama3.1:8b", description="Ollama model tag used for analysis tasks.")
    ollama_timeout_seconds: int = Field(900, description="Per-request timeout for Ollama calls (CPU inference is slow).")
    ollama_num_predict: int = Field(2048, description="Max tokens the LLM can generate per Ollama call.")
    ollama_num_ctx: int = Field(8192, description="Ollama context window (tokens). Must fit prompt + expected output.")
    llm_max_input_chars: int = Field(12000, description="Truncate document text before sending to the LLM to keep prompts small on CPU.")

    # ---- Local backend: LLM provider selector ----
    # "ollama" keeps the offline path. "gemini" uses Google Generative AI (needs GEMINI_API_KEY).
    local_llm_provider: Literal["ollama", "gemini"] = Field(
        "ollama", description="Which LLM to use when backend='local'."
    )

    # ---- Local backend: Gemini (LLM) ----
    gemini_api_key: str = Field("", description="Google AI Studio API key (used when local_llm_provider='gemini').")
    gemini_model: str = Field("gemini-3.5-flash", description="Gemini model id.")
    gemini_timeout_seconds: int = Field(120, description="Per-request timeout for Gemini calls.")
    gemini_max_output_tokens: int = Field(2048, description="Max output tokens for a single Gemini generation.")

    # ---- Local backend: sentence-transformers (embeddings) ----
    local_embedding_model: str = Field(
        "sentence-transformers/all-MiniLM-L6-v2",
        description="HuggingFace model id for local embeddings.",
    )
    local_embedding_dim: int = Field(384, description="Dimensions produced by local_embedding_model.")


# Module-level singleton — import this from anywhere
settings = Settings()
