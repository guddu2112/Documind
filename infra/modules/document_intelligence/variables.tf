variable "name" {
  type        = string
  description = "Name of the Document Intelligence resource"
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

variable "sku_name" {
  type        = string
  description = "SKU for Document Intelligence (F0 or S0)"
  default     = "S0"
}
