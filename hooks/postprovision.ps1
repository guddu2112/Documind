<#
.SYNOPSIS
    Post-provision hook — builds and pushes Docker image to ACR, then restarts
    the Container App to pick up the new image.

.DESCRIPTION
    Called automatically by `azd provision` (or `azd up`).
    Reads Terraform outputs via azd env to get ACR and Container App names.
#>

$ErrorActionPreference = "Stop"

Write-Host "==> Post-provision: building and pushing container image..." -ForegroundColor Cyan

# Read Terraform outputs that azd stores as env vars
$ACR_NAME       = (azd env get-value ACR_NAME 2>$null)
$ACR_LOGIN_SVR  = (azd env get-value ACR_LOGIN_SERVER 2>$null)

if (-not $ACR_NAME) {
    Write-Host "ACR_NAME not set — Container Apps not enabled. Skipping image push." -ForegroundColor Yellow
    exit 0
}

Write-Host "  ACR: $ACR_LOGIN_SVR"

# Build remotely in ACR (no local Docker required)
$IMAGE_TAG = "documind-api:latest"
Write-Host "==> Building image remotely in ACR: ${ACR_LOGIN_SVR}/${IMAGE_TAG}" -ForegroundColor Cyan
az acr build --registry $ACR_NAME --image $IMAGE_TAG --file Dockerfile .

Write-Host "==> Image built and pushed successfully." -ForegroundColor Green
