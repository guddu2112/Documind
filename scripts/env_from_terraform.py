#!/usr/bin/env python3
"""Generate a .env file from Terraform outputs.

Usage:
    python scripts/env_from_terraform.py          # writes .env
    python scripts/env_from_terraform.py --stdout  # prints to stdout

Reads ``terraform output -json`` from the ``infra/`` directory and maps
output names to environment variable names expected by DocuMind settings.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Map: terraform output name → env var name
_OUTPUT_MAP: dict[str, str] = {
    "ai_services_endpoint": "AZURE_OPENAI_ENDPOINT",
    "document_intelligence_endpoint": "AZURE_DOC_INTELLIGENCE_ENDPOINT",
    "ai_search_endpoint": "AZURE_SEARCH_ENDPOINT",
    "storage_account_name": "AZURE_STORAGE_ACCOUNT_NAME",
    "cosmos_db_endpoint": "AZURE_COSMOS_ENDPOINT",
    "keyvault_uri": "AZURE_KEYVAULT_URL",
    "application_insights_connection_string": "APPLICATIONINSIGHTS_CONNECTION_STRING",
    "acr_login_server": "ACR_LOGIN_SERVER",
    "acr_name": "ACR_NAME",
    "api_url": "API_URL",
}


def get_terraform_outputs(infra_dir: Path) -> dict[str, str]:
    """Run ``terraform output -json`` and return key→value mapping."""
    result = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=infra_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    raw = json.loads(result.stdout)
    return {
        k: v["value"]
        for k, v in raw.items()
        if v.get("value") is not None and v.get("value") != ""
    }


def generate_env(outputs: dict[str, str]) -> str:
    """Build .env file content from Terraform outputs."""
    lines = [
        "# Auto-generated from Terraform outputs",
        "# Re-run: make env-gen",
        "",
    ]
    for tf_name, env_name in sorted(_OUTPUT_MAP.items(), key=lambda x: x[1]):
        value = outputs.get(tf_name, "")
        lines.append(f"{env_name}={value}")

    # Add defaults not from Terraform
    lines.extend([
        "",
        "# Defaults (edit as needed)",
        "FOUNDRY_MODEL_DEPLOYMENT=gpt-4o",
        "AZURE_OPENAI_DEPLOYMENT=gpt-4o",
        "AZURE_OPENAI_API_VERSION=2024-12-01-preview",
        "AZURE_COSMOS_DATABASE=documind",
        "AZURE_COSMOS_CONTAINER=documents",
        "EMBEDDING_MODEL=text-embedding-3-small",
        "EMBEDDING_DIMENSIONS=1536",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    infra_dir = Path(__file__).resolve().parent.parent / "infra"
    if not infra_dir.is_dir():
        print(f"Error: infra directory not found at {infra_dir}", file=sys.stderr)
        sys.exit(1)

    outputs = get_terraform_outputs(infra_dir)
    env_content = generate_env(outputs)

    if "--stdout" in sys.argv:
        print(env_content)
    else:
        env_path = infra_dir.parent / ".env"
        env_path.write_text(env_content, encoding="utf-8")
        print(f"Wrote {env_path} with {len(outputs)} Terraform outputs")


if __name__ == "__main__":
    main()
