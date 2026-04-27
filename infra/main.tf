# -----------------------------------------------------------------------------
# DocuMind — Root Module
# Orchestrates all child modules for the document processing pipeline.
# -----------------------------------------------------------------------------

data "azurerm_client_config" "current" {}

# --- Resource Group ---

module "resource_group" {
  source = "./modules/resource_group"

  name     = "rg-${local.name_prefix}"
  location = var.location
  tags     = local.common_tags
}

# --- Monitoring (deploy early — other modules reference workspace ID) ---

module "monitoring" {
  source = "./modules/monitoring"

  name_prefix         = local.name_prefix
  resource_group_name = module.resource_group.name
  location            = module.resource_group.location
  tags                = local.common_tags
}

# --- Storage ---

module "storage" {
  source = "./modules/storage"

  name                = "${local.name_prefix_clean}st"
  resource_group_name = module.resource_group.name
  location            = module.resource_group.location
  tags                = local.common_tags
  containers          = ["raw-documents", "processed", "metadata"]
}

# --- Key Vault ---

module "keyvault" {
  source = "./modules/keyvault"

  name                = "${local.name_prefix}-kv"
  resource_group_name = module.resource_group.name
  location            = module.resource_group.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  tags                = local.common_tags
}

# --- AI Services (Azure OpenAI) ---

module "ai_services" {
  source = "./modules/ai_services"

  name                = "${local.name_prefix}-aoai"
  resource_group_name = module.resource_group.name
  location            = module.resource_group.location
  tags                = local.common_tags

  model_deployments = [
    {
      name          = var.gpt_model_name
      model_name    = var.gpt_model_name
      model_version = var.gpt_model_version
      sku_name      = "Standard"
      sku_capacity  = var.gpt_capacity
    },
    {
      name          = var.embedding_model_name
      model_name    = var.embedding_model_name
      model_version = var.embedding_model_version
      sku_name      = "Standard"
      sku_capacity  = 30
    }
  ]
}

# --- Document Intelligence ---

module "document_intelligence" {
  source = "./modules/document_intelligence"

  name                = "${local.name_prefix}-di"
  resource_group_name = module.resource_group.name
  location            = module.resource_group.location
  sku_name            = var.doc_intelligence_sku
  tags                = local.common_tags
}

# --- AI Search (optional — gated by feature toggle) ---
# Currently disabled: Cosmos DB vector search (DiskANN) handles search.
# Enable for future high-volume / hybrid search scenarios.

module "ai_search" {
  count  = var.enable_ai_search ? 1 : 0
  source = "./modules/ai_search"

  name                = "${local.name_prefix}-search"
  resource_group_name = module.resource_group.name
  location            = module.resource_group.location
  sku                 = var.search_sku
  semantic_search_sku = var.search_semantic_search
  tags                = local.common_tags
}

# --- Cosmos DB ---

module "cosmos_db" {
  source = "./modules/cosmos_db"

  account_name        = "${local.name_prefix}-cosmos"
  resource_group_name = module.resource_group.name
  location            = module.resource_group.location
  tags                = local.common_tags
}

# --- Container Apps (optional — gated by feature toggle) ---

module "container_apps" {
  count  = var.enable_container_apps ? 1 : 0
  source = "./modules/container_apps"

  name_prefix                = local.name_prefix
  resource_group_name        = module.resource_group.name
  location                   = module.resource_group.location
  log_analytics_workspace_id = module.monitoring.log_analytics_workspace_id
  tags                       = local.common_tags

  env_vars = {
    AZURE_OPENAI_ENDPOINT               = module.ai_services.endpoint
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT = module.document_intelligence.endpoint
    AZURE_SEARCH_ENDPOINT                = var.enable_ai_search ? module.ai_search[0].endpoint : ""
    AZURE_COSMOS_ENDPOINT                = module.cosmos_db.endpoint
    AZURE_STORAGE_ACCOUNT_NAME           = module.storage.name
    AZURE_KEYVAULT_URL                   = module.keyvault.vault_uri
    APPLICATIONINSIGHTS_CONNECTION_STRING = module.monitoring.application_insights_connection_string
  }
}

# --- Identity / RBAC ---
# Grant Container App's managed identity access to all services

module "identity" {
  count  = var.enable_container_apps ? 1 : 0
  source = "./modules/identity"

  resource_group_name = module.resource_group.name
  resource_group_id   = module.resource_group.id

  role_assignments = concat(
    [
      {
        principal_id = module.container_apps[0].api_identity_principal_id
        role_name    = "Cognitive Services OpenAI User"
        scope        = module.ai_services.id
        description  = "Allow API to call Azure OpenAI"
      },
      {
        principal_id = module.container_apps[0].api_identity_principal_id
        role_name    = "Cognitive Services User"
        scope        = module.document_intelligence.id
        description  = "Allow API to call Document Intelligence"
      },
      {
        principal_id = module.container_apps[0].api_identity_principal_id
        role_name    = "Storage Blob Data Contributor"
        scope        = module.storage.id
        description  = "Allow API to read/write blobs"
      },
      {
        principal_id = module.container_apps[0].api_identity_principal_id
        role_name    = "Key Vault Secrets User"
        scope        = module.keyvault.id
        description  = "Allow API to read Key Vault secrets"
      },
    ],
    # AI Search RBAC — only when AI Search is provisioned
    var.enable_ai_search ? [
      {
        principal_id = module.container_apps[0].api_identity_principal_id
        role_name    = "Search Index Data Contributor"
        scope        = module.ai_search[0].id
        description  = "Allow API to read/write search indexes"
      },
    ] : [],
  )
}
