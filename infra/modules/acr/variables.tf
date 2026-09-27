variable "name_prefix" {
  type        = string
  description = "Prefix for the ACR name (hyphens will be stripped)"
}

variable "resource_group_name" {
  type        = string
  description = "Name of the resource group"
}

variable "location" {
  type        = string
  description = "Azure region"
}

variable "sku" {
  type        = string
  description = "ACR SKU tier"
  default     = "Basic"

  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.sku)
    error_message = "ACR SKU must be one of: Basic, Standard, Premium."
  }
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
