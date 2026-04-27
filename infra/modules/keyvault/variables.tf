variable "name" {
  type        = string
  description = "Name of the Key Vault"
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

variable "tenant_id" {
  type        = string
  description = "Azure AD tenant ID"
}

variable "sku_name" {
  type        = string
  description = "Key Vault SKU (standard or premium)"
  default     = "standard"
}

variable "purge_protection_enabled" {
  type        = bool
  description = "Enable purge protection"
  default     = true
}

variable "soft_delete_retention_days" {
  type        = number
  description = "Number of days to retain soft-deleted items"
  default     = 90
}
