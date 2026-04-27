output "id" {
  description = "Cosmos DB account ID"
  value       = azurerm_cosmosdb_account.this.id
}

output "name" {
  description = "Cosmos DB account name"
  value       = azurerm_cosmosdb_account.this.name
}

output "endpoint" {
  description = "Cosmos DB endpoint"
  value       = azurerm_cosmosdb_account.this.endpoint
}

output "primary_key" {
  description = "Cosmos DB primary key"
  value       = azurerm_cosmosdb_account.this.primary_key
  sensitive   = true
}

output "database_name" {
  description = "Cosmos DB database name"
  value       = azurerm_cosmosdb_sql_database.this.name
}

output "identity_principal_id" {
  description = "System-assigned managed identity principal ID"
  value       = azurerm_cosmosdb_account.this.identity[0].principal_id
}
