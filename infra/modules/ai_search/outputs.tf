output "id" {
  description = "AI Search service ID"
  value       = azurerm_search_service.this.id
}

output "name" {
  description = "AI Search service name"
  value       = azurerm_search_service.this.name
}

output "endpoint" {
  description = "AI Search endpoint URL"
  value       = "https://${azurerm_search_service.this.name}.search.windows.net"
}

output "primary_key" {
  description = "Primary admin key"
  value       = azurerm_search_service.this.primary_key
  sensitive   = true
}

output "identity_principal_id" {
  description = "System-assigned managed identity principal ID"
  value       = azurerm_search_service.this.identity[0].principal_id
}
