locals {
  # Naming convention: {project}-{resource_abbreviation}-{environment}
  name_prefix = "${var.project_name}-${var.environment}"
  name_suffix = var.location

  # Sanitized name for resources that don't allow hyphens (storage, cosmos, etc.)
  name_prefix_clean = replace(local.name_prefix, "-", "")

  # Common tags applied to all resources
  common_tags = merge(var.tags, {
    environment = var.environment
    project     = var.project_name
    managed_by  = "terraform"
  })
}
