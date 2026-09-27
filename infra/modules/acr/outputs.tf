output "id" {
  description = "Container Registry resource ID"
  value       = azurerm_container_registry.this.id
}

output "name" {
  description = "Container Registry name"
  value       = azurerm_container_registry.this.name
}

output "login_server" {
  description = "Container Registry login server URL"
  value       = azurerm_container_registry.this.login_server
}

output "admin_username" {
  description = "Container Registry admin username"
  value       = azurerm_container_registry.this.admin_username
}

output "admin_password" {
  description = "Container Registry admin password"
  value       = azurerm_container_registry.this.admin_password
  sensitive   = true
}
