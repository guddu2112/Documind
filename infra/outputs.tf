# --- Resource Group ---

output "resource_group_name" {
  description = "Name of the resource group"
  value       = module.resource_group.name
}

# --- AI Services (Azure OpenAI) ---

output "ai_services_endpoint" {
  description = "Azure OpenAI endpoint URL"
  value       = module.ai_services.endpoint
}

output "ai_services_name" {
  description = "Azure OpenAI account name"
  value       = module.ai_services.name
}

# --- Document Intelligence ---

output "document_intelligence_endpoint" {
  description = "Document Intelligence endpoint URL"
  value       = module.document_intelligence.endpoint
}

# --- AI Search (conditional) ---

output "ai_search_endpoint" {
  description = "Azure AI Search endpoint URL (if AI Search enabled)"
  value       = var.enable_ai_search ? module.ai_search[0].endpoint : null
}

output "ai_search_name" {
  description = "Azure AI Search service name (if AI Search enabled)"
  value       = var.enable_ai_search ? module.ai_search[0].name : null
}

# --- Storage ---

output "storage_account_name" {
  description = "Storage account name"
  value       = module.storage.name
}

output "storage_blob_endpoint" {
  description = "Blob storage endpoint URL"
  value       = module.storage.primary_blob_endpoint
}

# --- Cosmos DB ---

output "cosmos_db_endpoint" {
  description = "Cosmos DB endpoint URL"
  value       = module.cosmos_db.endpoint
}

output "cosmos_db_database_name" {
  description = "Cosmos DB database name"
  value       = module.cosmos_db.database_name
}

# --- Key Vault ---

output "keyvault_uri" {
  description = "Key Vault URI"
  value       = module.keyvault.vault_uri
}

# --- Monitoring ---

output "application_insights_connection_string" {
  description = "Application Insights connection string (for OTEL exporter)"
  value       = module.monitoring.application_insights_connection_string
  sensitive   = true
}

# --- Container Apps (conditional) ---

output "api_url" {
  description = "API endpoint URL (if Container Apps enabled)"
  value       = var.enable_container_apps ? module.container_apps[0].api_url : null
}
