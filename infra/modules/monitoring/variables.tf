variable "name_prefix" {
  type        = string
  description = "Prefix for monitoring resource names"
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

variable "retention_in_days" {
  type        = number
  description = "Log Analytics workspace data retention in days"
  default     = 30
}
