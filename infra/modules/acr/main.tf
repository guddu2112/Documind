# -----------------------------------------------------------------------------
# Azure Container Registry
# Stores Docker images for Container Apps deployment.
# -----------------------------------------------------------------------------

resource "azurerm_container_registry" "this" {
  name                = replace("${var.name_prefix}acr", "-", "")
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = var.sku
  admin_enabled       = true

  tags = var.tags
}
