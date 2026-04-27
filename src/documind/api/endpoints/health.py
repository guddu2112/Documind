"""Health and readiness probe endpoints.

Routes:
    GET /health — Liveness probe (always 200).
    GET /ready  — Readiness probe (checks Azure dependencies).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from documind.api.schemas import HealthResponse, ReadinessCheck, ReadinessResponse
from documind.core.config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
)
async def health():
    """Returns 200 immediately — confirms the process is alive."""
    return HealthResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe — checks backend connectivity",
)
async def readiness():
    """Check connectivity to Cosmos DB, Blob Storage, and Azure OpenAI.

    Returns 200 with ``status: ready`` if all checks pass, or 200 with
    ``status: degraded`` and details for each failing check.  We return
    200 even when degraded so the probe body is always readable.
    """
    checks: list[ReadinessCheck] = []

    # ── Cosmos DB ───────────────────────────────────────────────
    checks.append(await _check_cosmos())

    # ── Blob Storage ────────────────────────────────────────────
    checks.append(await _check_blob())

    # ── Azure OpenAI ────────────────────────────────────────────
    checks.append(await _check_openai())

    all_ok = all(c.status == "ok" for c in checks)
    return ReadinessResponse(
        status="ready" if all_ok else "degraded",
        checks=checks,
    )


# ── Individual checks ──────────────────────────────────────────────


async def _check_cosmos() -> ReadinessCheck:
    """Verify Cosmos DB is reachable by listing databases."""
    try:
        from azure.cosmos import CosmosClient

        if settings.azure_cosmos_key:
            client = CosmosClient(settings.azure_cosmos_endpoint, settings.azure_cosmos_key)
        else:
            from azure.identity import DefaultAzureCredential
            client = CosmosClient(settings.azure_cosmos_endpoint, DefaultAzureCredential())

        # A lightweight call — just reads metadata
        list(client.list_databases())
        return ReadinessCheck(name="cosmos_db", status="ok")
    except Exception as exc:
        logger.warning("Cosmos readiness check failed: %s", exc)
        return ReadinessCheck(name="cosmos_db", status="error", detail=str(exc))


async def _check_blob() -> ReadinessCheck:
    """Verify Blob Storage is reachable by listing containers."""
    try:
        from azure.storage.blob import BlobServiceClient

        if settings.azure_storage_connection_string:
            client = BlobServiceClient.from_connection_string(
                settings.azure_storage_connection_string
            )
        else:
            from azure.identity import DefaultAzureCredential
            account_url = f"https://{settings.azure_storage_account_name}.blob.core.windows.net"
            client = BlobServiceClient(account_url, credential=DefaultAzureCredential())

        # A lightweight call — just lists container names
        list(client.list_containers(results_per_page=1))
        return ReadinessCheck(name="blob_storage", status="ok")
    except Exception as exc:
        logger.warning("Blob readiness check failed: %s", exc)
        return ReadinessCheck(name="blob_storage", status="error", detail=str(exc))


async def _check_openai() -> ReadinessCheck:
    """Verify Azure OpenAI endpoint is reachable."""
    try:
        import httpx

        endpoint = settings.azure_openai_endpoint.rstrip("/")
        if not endpoint:
            return ReadinessCheck(
                name="azure_openai", status="error", detail="Endpoint not configured"
            )

        # Hit the openai health endpoint (returns 200 if the service is up)
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{endpoint}/openai/models?api-version=2024-02-01")
            if resp.status_code < 500:
                return ReadinessCheck(name="azure_openai", status="ok")
            return ReadinessCheck(
                name="azure_openai",
                status="error",
                detail=f"HTTP {resp.status_code}",
            )
    except Exception as exc:
        logger.warning("OpenAI readiness check failed: %s", exc)
        return ReadinessCheck(name="azure_openai", status="error", detail=str(exc))
