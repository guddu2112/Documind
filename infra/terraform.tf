terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.14"
    }
    azapi = {
      source  = "azure/azapi"
      version = "~> 2.0"
    }
  }

  # Configure backend via CLI:
  #   terraform init -backend-config="backend.hcl"
  #
  # Example backend.hcl:
  #   resource_group_name  = "rg-documind-tfstate"
  #   storage_account_name = "stdocumindtfstate"
  #   container_name       = "tfstate"
  #   key                  = "documind.terraform.tfstate"
  # backend "azurerm" {}
  # NOTE: Using local state for dev. Uncomment above for shared/remote state.
}
