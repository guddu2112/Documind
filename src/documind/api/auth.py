"""Authentication middleware for the DocuMind API.

Supports two modes configured via the ``AUTH_MODE`` env var:

- ``api_key``  — (default) Validates an ``X-API-Key`` header against a
  secret stored in Azure Key Vault.
- ``entra_id`` — Validates an Azure Entra ID (AAD) bearer token.
- ``none``     — No authentication (local development only).

Usage in endpoints::

    from documind.api.auth import require_auth

    @router.get("/protected")
    async def protected(user=Depends(require_auth)):
        ...
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from documind.core.config.settings import settings

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────

AUTH_MODE = os.getenv("AUTH_MODE", "api_key")  # api_key | entra_id | none

# ── API Key auth ───────────────────────────────────────────────────

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Cached API key from Key Vault
_cached_api_key: Optional[str] = None


def _get_api_key_from_vault() -> str:
    """Retrieve the API key from Azure Key Vault.

    The key is cached after the first call to avoid repeated vault
    lookups on every request.
    """
    global _cached_api_key
    if _cached_api_key is not None:
        return _cached_api_key

    # Allow override via env var for local dev
    env_key = os.getenv("DOCUMIND_API_KEY")
    if env_key:
        _cached_api_key = env_key
        return _cached_api_key

    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=settings.azure_keyvault_url, credential=credential)
        secret = client.get_secret("documind-api-key")
        _cached_api_key = secret.value
        logger.info("API key loaded from Key Vault")
        return _cached_api_key
    except Exception as exc:
        logger.error("Failed to load API key from Key Vault: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable.",
        ) from exc


async def _validate_api_key(
    api_key: Optional[str] = Security(_api_key_header),
) -> str:
    """Validate the X-API-Key header against the stored secret."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
        )

    expected = _get_api_key_from_vault()
    if not _constant_time_compare(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )

    return api_key


def _constant_time_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    import hmac
    return hmac.compare_digest(a.encode(), b.encode())


# ── Entra ID (AAD) auth ───────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


async def _validate_entra_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer_scheme),
) -> dict:
    """Validate an Azure Entra ID bearer token.

    Uses the ``azure-identity`` library to validate the JWT against
    the configured tenant.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        import jwt
        from jwt import PyJWKClient

        # Azure AD v2.0 JWKS endpoint
        tenant_id = os.getenv("AZURE_TENANT_ID", "common")
        jwks_url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        jwks_client = PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=os.getenv("AZURE_CLIENT_ID", ""),
            options={"verify_exp": True},
        )
        return claims
    except Exception as exc:
        logger.warning("Entra ID token validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ── No-auth (dev mode) ────────────────────────────────────────────


async def _no_auth() -> str:
    """Bypass authentication entirely — development only."""
    return "anonymous"


# ── Public dependency ──────────────────────────────────────────────


def require_auth():
    """Return the appropriate auth dependency based on AUTH_MODE.

    This is a dependency *factory* — use it with ``Depends(require_auth())``.
    """
    if AUTH_MODE == "none":
        return Depends(_no_auth)
    elif AUTH_MODE == "entra_id":
        return Depends(_validate_entra_token)
    else:
        return Depends(_validate_api_key)


# Pre-built dependency for convenience
auth_dependency = require_auth()
