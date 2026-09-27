"""Application settings loaded from environment variables.

Uses pydantic-settings so every value can be overridden via env vars or a
.env file.  ``load_dotenv(override=False)`` is called so that runtime env
vars (e.g. from Container Apps) always take precedence over the .env file.
"""

from __future__ import annotations

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


# Module-level singleton — import this from anywhere
settings = Settings()
