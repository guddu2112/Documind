variable "account_name" {
  type        = string
  description = "Name of the Cosmos DB account"
}

variable "resource_group_name" {
  type        = string
  description = "Name of the resource group"
}

variable "location" {
  type        = string
  description = "Azure region"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}

variable "database_name" {
  type        = string
  description = "Name of the Cosmos DB database"
  default     = "documind"
}

variable "containers" {
  type = list(object({
    name               = string
    partition_key_path = string
  }))
  description = "List of containers to create"
  default = [
    { name = "pipeline-state", partition_key_path = "/documentId" },
    { name = "documents", partition_key_path = "/documentType" },
    { name = "audit-trail", partition_key_path = "/documentId" },
    { name = "search_index", partition_key_path = "/doc_type" }
  ]
}

variable "max_throughput" {
  type        = number
  description = "Maximum autoscale throughput (RU/s) for the database"
  default     = 1000
}
