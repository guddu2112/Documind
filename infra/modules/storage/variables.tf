variable "name" {
  type        = string
  description = "Name of the storage account (must be globally unique, 3-24 lowercase alphanumeric)"
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

variable "account_tier" {
  type        = string
  description = "Storage account tier"
  default     = "Standard"
}

variable "replication_type" {
  type        = string
  description = "Storage replication type"
  default     = "LRS"
}

variable "containers" {
  type        = list(string)
  description = "List of blob container names to create"
  default     = ["raw-documents", "processed", "metadata"]
}
