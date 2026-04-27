output "environment_id" {
  description = "Container Apps environment ID"
  value       = azurerm_container_app_environment.this.id
}

output "api_fqdn" {
  description = "API container app fully qualified domain name"
  value       = azurerm_container_app.api.ingress[0].fqdn
}

output "api_url" {
  description = "API container app URL"
  value       = "https://${azurerm_container_app.api.ingress[0].fqdn}"
}

output "api_identity_principal_id" {
  description = "API container app system-assigned managed identity principal ID"
  value       = azurerm_container_app.api.identity[0].principal_id
}
