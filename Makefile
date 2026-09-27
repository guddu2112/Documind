# DocuMind — Intelligent Document Processing Pipeline
# ────────────────────────────────────────────────────
# Common commands for development and deployment.

.DEFAULT_GOAL := help

PYTHON   ?= .venv/Scripts/python
PYTEST   ?= $(PYTHON) -m pytest
UVICORN  ?= $(PYTHON) -m uvicorn
PORT     ?= 8000
ACR_NAME ?= $(shell cd infra && terraform output -raw acr_name 2>/dev/null)
ACR_SVR  ?= $(shell cd infra && terraform output -raw acr_login_server 2>/dev/null)

# ── Development ─────────────────────────────────────

.PHONY: install
install: ## Install all dependencies (prod + dev)
	python -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

.PHONY: dev
dev: ## Start API (port 8000) + frontend (port 3000) in parallel
	$(MAKE) -j2 run web-dev

.PHONY: run
run: ## Start the API server (default port 8000)
	$(UVICORN) documind.api.main:app --host 127.0.0.1 --port $(PORT) --reload

.PHONY: test
test: ## Run unit tests (no Azure credentials needed)
	$(PYTEST) tests/ -v --tb=short --ignore=tests/e2e

.PHONY: test-cov
test-cov: ## Run unit tests with coverage report
	$(PYTEST) tests/ --cov=documind --cov-report=term-missing --ignore=tests/e2e

.PHONY: test-e2e
test-e2e: ## Run E2E tests against live Azure services (requires .env)
	$(PYTEST) tests/e2e/ -v --tb=short --e2e --timeout=300

.PHONY: test-all
test-all: ## Run unit + E2E tests
	$(PYTEST) tests/ -v --tb=short --e2e --timeout=300

.PHONY: lint
lint: ## Run ruff linter
	$(PYTHON) -m ruff check src/ tests/

.PHONY: format
format: ## Auto-format code with ruff
	$(PYTHON) -m ruff format src/ tests/

.PHONY: typecheck
typecheck: ## Run mypy type checking
	$(PYTHON) -m mypy src/documind/

# ── MCP Server ──────────────────────────────────────

.PHONY: mcp
mcp: ## Start the MCP server (stdio transport)
	$(PYTHON) -m documind.mcp

.PHONY: mcp-sse
mcp-sse: ## Start the MCP server (SSE transport)
	$(PYTHON) -m documind.mcp --sse

.PHONY: mcp-http
mcp-http: ## Start API + MCP server on port 8000 (Streamable HTTP at /mcp)
	$(UVICORN) documind.api.main:app --host 127.0.0.1 --port $(PORT) --reload

# ── Scaffolding ─────────────────────────────────────

.PHONY: add-doctype
add-doctype: ## Scaffold a new doc type (usage: make add-doctype NAME=invoice DISPLAY="Invoice")
	$(PYTHON) scripts/add_doctype.py $(NAME) "$(DISPLAY)" $(if $(TASKS),--tasks $(TASKS)) $(if $(FORMATS),--formats $(FORMATS))

# ── Infrastructure ──────────────────────────────────

.PHONY: infra-init
infra-init: ## Terraform init (supports local + remote backend)
	cd infra && terraform init

.PHONY: infra-plan
infra-plan: ## Terraform plan for dev environment
	cd infra && terraform plan -var-file="environments/dev.tfvars"

.PHONY: infra-apply
infra-apply: ## Terraform apply for dev environment
	cd infra && terraform apply -var-file="environments/dev.tfvars"

# ── Docker ──────────────────────────────────────────

.PHONY: docker-build
docker-build: ## Build Docker image
	docker build -t documind:latest .

.PHONY: docker-push
docker-push: docker-build ## Build + push image to ACR
	az acr login --name $(ACR_NAME)
	docker tag documind:latest $(ACR_SVR)/documind-api:latest
	docker push $(ACR_SVR)/documind-api:latest

.PHONY: docker-run
docker-run: ## Run Docker container locally
	docker run --env-file .env -p $(PORT):8000 documind:latest

# ── Deployment ──────────────────────────────────────

.PHONY: deploy
deploy: ## Full deployment via azd up (provision infra + build + push)
	azd up

.PHONY: provision
provision: ## Provision Azure infrastructure only
	azd provision

.PHONY: env-gen
env-gen: ## Generate .env from Terraform outputs
	$(PYTHON) scripts/env_from_terraform.py

# ── Utilities ───────────────────────────────────────

.PHONY: clean
clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .ruff_cache htmlcov .coverage

# ── Web Frontend ────────────────────────────────────

.PHONY: web-install
web-install: ## Install web frontend dependencies
	cd web && npm install

.PHONY: web-dev
web-dev: ## Start Vite dev server (port 3000, proxies to API)
	cd web && npm run dev

.PHONY: web-build
web-build: ## Build web frontend for production
	cd web && npm run build

.PHONY: help
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
