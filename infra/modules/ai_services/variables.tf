variable "name" {
  type        = string
  description = "Name of the Azure AI Services (Cognitive Services) account"
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
  description = "SKU for AI Services"
  default     = "S0"
}

variable "model_deployments" {
  type = list(object({
    name           = string
    model_name     = string
    model_version  = string
    sku_name       = optional(string, "Standard")
    sku_capacity   = optional(number, 30)
  }))
  description = "List of model deployments (GPT, embedding, etc.)"
  default     = []
}
