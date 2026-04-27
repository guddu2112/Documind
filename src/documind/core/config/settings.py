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


# Module-level singleton — import this from anywhere
settings = Settings()
