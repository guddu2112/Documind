variable "name_prefix" {
  type        = string
  description = "Prefix for Container Apps resource names"
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

variable "log_analytics_workspace_id" {
  type        = string
  description = "Log Analytics workspace ID for Container Apps environment"
}

variable "container_image" {
  type        = string
  description = "Container image to deploy"
  default     = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
}

variable "container_port" {
  type        = number
  description = "Port the container listens on"
  default     = 8000
}

variable "cpu" {
  type        = number
  description = "CPU cores allocated to the container"
  default     = 0.5
}

variable "memory" {
  type        = string
  description = "Memory allocated to the container"
  default     = "1Gi"
}

variable "min_replicas" {
  type        = number
  description = "Minimum number of replicas"
  default     = 0
}

variable "max_replicas" {
  type        = number
  description = "Maximum number of replicas"
  default     = 3
}

variable "acr_login_server" {
  type        = string
  description = "ACR login server URL for image pull"
  default     = ""
}

variable "acr_identity" {
  type        = string
  description = "Identity type for ACR pull (system for managed identity)"
  default     = "system"
}

variable "acr_admin_username" {
  type        = string
  description = "ACR admin username for image pull"
  default     = ""
}

variable "acr_admin_password" {
  type        = string
  description = "ACR admin password for image pull"
  default     = ""
  sensitive   = true
}

variable "env_vars" {
  type        = map(string)
  description = "Environment variables for the container"
  default     = {}
}
