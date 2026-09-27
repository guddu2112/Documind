#!/usr/bin/env bash
#
# Post-provision hook — builds and pushes Docker image to ACR.
# Called automatically by `azd provision` (or `azd up`).
#
set -euo pipefail

echo "==> Post-provision: building and pushing container image..."

# Read Terraform outputs that azd stores as env vars
ACR_NAME=$(azd env get-value ACR_NAME 2>/dev/null || true)
ACR_LOGIN_SVR=$(azd env get-value ACR_LOGIN_SERVER 2>/dev/null || true)

if [ -z "$ACR_NAME" ]; then
    echo "ACR_NAME not set — Container Apps not enabled. Skipping image push."
    exit 0
fi

echo "  ACR: $ACR_LOGIN_SVR"

# Build remotely in ACR (no local Docker required)
IMAGE_TAG="documind-api:latest"
echo "==> Building image remotely in ACR: ${ACR_LOGIN_SVR}/${IMAGE_TAG}"
az acr build --registry "$ACR_NAME" --image "$IMAGE_TAG" --file Dockerfile .

echo "==> Image built and pushed successfully."
