variable "environment" {
  type        = string
  description = "Environment name (dev, staging, prod)"
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "location" {
  type        = string
  description = "Azure region for all resources"
  default     = "eastus2"
}

variable "project_name" {
  type        = string
  description = "Name of the project, used as prefix for all resources"
  default     = "documind"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,14}$", var.project_name))
    error_message = "Project name must be 3-15 lowercase alphanumeric characters, starting with a letter."
  }
}

variable "tags" {
  type        = map(string)
  description = "Additional tags to apply to all resources"
  default     = {}
}

# --- AI Services ---

variable "gpt_model_name" {
  type        = string
  description = "GPT model deployment name"
  default     = "gpt-4o"
}

variable "gpt_model_version" {
  type        = string
  description = "GPT model version to deploy"
  default     = "2024-11-20"
}

variable "gpt_capacity" {
  type        = number
  description = "TPM capacity (in thousands) for the GPT model deployment"
  default     = 30
}

variable "embedding_model_name" {
  type        = string
  description = "Embedding model deployment name for vector search"
  default     = "text-embedding-3-small"
}

variable "embedding_model_version" {
  type        = string
  description = "Embedding model version"
  default     = "1"
}

# --- Service SKUs ---

variable "doc_intelligence_sku" {
  type        = string
  description = "SKU for Azure Document Intelligence"
  default     = "S0"

  validation {
    condition     = contains(["F0", "S0"], var.doc_intelligence_sku)
    error_message = "Document Intelligence SKU must be F0 (free) or S0 (standard)."
  }
}

variable "search_sku" {
  type        = string
  description = "SKU for Azure AI Search"
  default     = "standard"

  validation {
    condition     = contains(["basic", "standard", "standard2", "standard3"], var.search_sku)
    error_message = "Search SKU must be one of: basic, standard, standard2, standard3."
  }
}

variable "search_semantic_search" {
  type        = string
  description = "Semantic search tier for Azure AI Search"
  default     = "standard"

  validation {
    condition     = contains(["disabled", "free", "standard"], var.search_semantic_search)
    error_message = "Semantic search must be one of: disabled, free, standard."
  }
}

# --- Feature Toggles ---

variable "enable_ai_search" {
  type        = bool
  description = "Whether to provision Azure AI Search (disabled by default — Cosmos DB vector search is used instead; enable for future high-volume/hybrid scenarios)"
  default     = false
}

variable "enable_container_apps" {
  type        = bool
  description = "Whether to provision Container Apps environment for API hosting"
  default     = false
}

variable "enable_private_endpoints" {
  type        = bool
  description = "Whether to enable private endpoints for all services (for production)"
  default     = false
}
