output "id" {
  description = "AI Services account ID"
  value       = azurerm_cognitive_account.this.id
}

output "name" {
  description = "AI Services account name"
  value       = azurerm_cognitive_account.this.name
}

output "endpoint" {
  description = "AI Services endpoint URL"
  value       = azurerm_cognitive_account.this.endpoint
}

output "primary_access_key" {
  description = "Primary access key"
  value       = azurerm_cognitive_account.this.primary_access_key
  sensitive   = true
}

output "identity_principal_id" {
  description = "System-assigned managed identity principal ID"
  value       = azurerm_cognitive_account.this.identity[0].principal_id
}
