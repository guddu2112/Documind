variable "name" {
  type        = string
  description = "Name of the Azure AI Search service"
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

variable "sku" {
  type        = string
  description = "SKU for AI Search (basic, standard, standard2, standard3)"
  default     = "standard"
}

variable "replica_count" {
  type        = number
  description = "Number of replicas"
  default     = 1
}

variable "partition_count" {
  type        = number
  description = "Number of partitions"
  default     = 1
}

variable "semantic_search_sku" {
  type        = string
  description = "Semantic search tier (disabled, free, standard)"
  default     = "standard"
}
