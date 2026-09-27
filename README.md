# DocuMind — Intelligent Document Processing Pipeline

> Multi-Agent AI Accelerator for RFPs, Contracts & Specifications

## Overview

DocuMind is a reusable practice accelerator that automates document review using a multi-agent AI pipeline built on Azure. It targets the pain of manual document review across client engagements — RFPs, contracts, and technical specifications — delivering ~60% reduction in review time.

### Key Features

- **Multi-agent pipeline** — Ingestion → Extraction → Analysis → Search, orchestrated end-to-end
- **Pluggable document types** — Add new doc types via YAML config, no code changes
- **MCP server** — Expose analysis tools at `/mcp` for AI assistants (Copilot, Claude, etc.)
- **React SPA frontend** — Upload, track progress, view results with real-time status polling
- **One-command deployment** — `azd up` provisions all Azure infra, builds & pushes container
- **Managed identity everywhere** — Zero secrets in config; all Azure services use RBAC

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.11+ |
| **Agent Framework** | Microsoft Agent Framework |
| **API** | FastAPI + uvicorn |
| **MCP** | FastMCP (Streamable HTTP, mounted at `/mcp`) |
| **Frontend** | React 19 + TypeScript + Vite 8 + Tailwind CSS v4 |
| **IaC** | Terraform (~> 4.14) — 11 modules |
| **Deployment** | Azure Developer CLI (`azd`) → ACR → Container Apps |
| **CI/CD** | GitHub Actions |

## Azure Services

| Service | Purpose |
|---------|---------|
| **Azure AI Foundry / OpenAI (GPT-4o)** | Summarization, risk analysis, clause extraction |
| **Azure Document Intelligence** | OCR, layout, table & key-value extraction |
| **Azure Cosmos DB** | Pipeline state, metadata, vector search (DiskANN) |
| **Azure Blob Storage** | Raw & processed document storage |
| **Azure Container Registry** | Docker image hosting |
| **Azure Container Apps** | API hosting with managed identity |
| **Azure Key Vault** | Secrets management |
| **Azure Monitor + App Insights** | Observability, distributed tracing |
| **Azure AI Search** | *(optional)* Semantic + vector search (feature-flagged) |

## Project Structure

```
documind/
├── infra/                    # Terraform modules (11 modules)
│   ├── modules/
│   │   ├── acr/              # Azure Container Registry
│   │   ├── ai_search/        # AI Search (optional)
│   │   ├── ai_services/      # Azure OpenAI
│   │   ├── container_apps/   # Container Apps Environment + App
│   │   ├── cosmos_db/        # Cosmos DB (NoSQL + vector)
│   │   ├── document_intelligence/
│   │   ├── identity/         # RBAC role assignments
│   │   ├── keyvault/         # Key Vault
│   │   ├── monitoring/       # Log Analytics + App Insights
│   │   ├── resource_group/
│   │   └── storage/          # Blob Storage
│   └── environments/         # dev.tfvars, prod.tfvars
├── src/documind/
│   ├── core/                 # Settings, protocols, tracing
│   ├── agents/               # Pipeline agents
│   │   ├── ingestion/        # Upload, classify, store
│   │   ├── extraction/       # OCR, layout, tables
│   │   ├── analysis/         # Summarize, risks, clauses
│   │   ├── search/           # Index, vector search
│   │   └── orchestrator/     # Pipeline workflow coordinator
│   ├── services/             # Azure SDK wrappers
│   ├── doctypes/             # YAML-driven doc-type registry
│   ├── mcp/                  # MCP server (tools for AI assistants)
│   └── api/                  # FastAPI endpoints
├── web/                      # React SPA frontend
├── hooks/                    # azd lifecycle hooks
├── scripts/                  # Utility scripts
├── tests/                    # Unit & integration tests
├── config/                   # Doc-type configurations
├── Dockerfile                # Multi-stage (Python + Node + runtime)
├── Makefile                  # Developer workflow automation
├── azure.yaml                # azd project definition
└── .env.template             # Environment variable reference
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend build)
- [Azure Developer CLI (`azd`)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- [Terraform ≥ 1.6](https://www.terraform.io/downloads)
- [Docker](https://docs.docker.com/get-docker/)
- Azure subscription with Azure OpenAI access

### One-Command Deploy

```bash
azd auth login
azd up
```

This provisions all Azure resources (Terraform), builds the Docker image,
pushes to ACR, and deploys to Container Apps. The API URL is printed at
the end.

### Local Development

```bash
# Install Python + frontend dependencies
make install
cd web && npm install && cd ..

# Copy and fill in environment variables
cp .env.template .env
# Edit .env with your Azure resource endpoints

# Start API (port 8000) + frontend (port 3000) in parallel
make dev

# Or start them separately:
make run        # API only
make web-dev    # Frontend only (proxies to API)
```

### Generate .env from Terraform

After provisioning infrastructure, generate a `.env` file automatically:

```bash
make env-gen
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/ready` | Readiness probe |
| `POST` | `/documents/upload` | Upload a document for processing |
| `GET` | `/documents/{id}/status` | Poll processing status |
| `GET` | `/documents/{id}` | Get processed document results |
| `POST` | `/search` | Search across processed documents |
| `GET` | `/events/{id}` | SSE stream for real-time updates |
| `POST` | `/mcp` | MCP endpoint (Streamable HTTP) |

## MCP Server

DocuMind exposes analysis tools via the [Model Context Protocol](https://modelcontextprotocol.io/) at `/mcp`. AI assistants (Copilot, Claude, etc.) can use these tools:

| Tool | Description |
|------|-------------|
| `list_doc_types` | Enumerate configured document types and their tasks |
| `summarize` | Generate executive summary of a document |
| `extract_clauses` | Extract and categorise contract clauses |
| `check_compliance` | Check specification compliance |

The MCP server is automatically mounted on the FastAPI app — no separate process needed.

## Agents

| Agent | Responsibility | Azure Service |
|-------|---------------|---------------|
| **Ingestion** | Upload, classify, store documents | Azure Blob Storage |
| **Extraction** | OCR, layout, table/key-value extraction | Azure Document Intelligence |
| **Analysis** | Summarize, identify risks, extract clauses | Azure OpenAI (GPT-4o) |
| **Search** | Vector index and semantic search | Azure Cosmos DB (DiskANN) |
| **Orchestrator** | Sequential workflow coordination | Agent Framework |

## Adding a New Document Type

Document types are defined as YAML files in `src/documind/doctypes/types/`. No code changes required — the pipeline auto-discovers new types.

```bash
# Scaffold a new doc type
make add-doctype NAME=invoice DISPLAY="Invoice"
```

See [add_new_doc_type_in_documind.md](add_new_doc_type_in_documind.md) for the full guide.

## Terraform Modules

| Module | Purpose | Feature Flag |
|--------|---------|-------------|
| `resource_group` | Resource group | Always |
| `monitoring` | Log Analytics + App Insights | Always |
| `storage` | Blob Storage (3 containers) | Always |
| `keyvault` | Key Vault | Always |
| `ai_services` | Azure OpenAI (GPT-4o + embedding) | Always |
| `document_intelligence` | Document Intelligence | Always |
| `cosmos_db` | Cosmos DB (NoSQL + vector search) | Always |
| `acr` | Azure Container Registry | `enable_container_apps` |
| `container_apps` | Container Apps Environment + App | `enable_container_apps` |
| `identity` | RBAC role assignments (7 roles) | `enable_container_apps` |
| `ai_search` | Azure AI Search | `enable_ai_search` |

## Makefile Targets

```
make install      Install dependencies (prod + dev)
make dev          API + frontend in parallel
make run          API server only (port 8000)
make test         Run tests
make lint         Run ruff linter
make format       Auto-format code
make deploy       Full deployment (azd up)
make provision    Provision infrastructure only
make docker-build Build Docker image
make docker-push  Build + push to ACR
make infra-init   Terraform init
make infra-plan   Terraform plan (dev)
make infra-apply  Terraform apply (dev)
make env-gen      Generate .env from Terraform outputs
make mcp-http     API + MCP server (Streamable HTTP at /mcp)
make web-install  Install frontend dependencies
make web-dev      Vite dev server (port 3000)
make web-build    Build frontend for production
make add-doctype  Scaffold a new doc type
```

## Environment Variables

See [.env.template](.env.template) for the full reference. Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint | *(required)* |
| `AZURE_DOC_INTELLIGENCE_ENDPOINT` | Document Intelligence endpoint | *(required)* |
| `AZURE_COSMOS_ENDPOINT` | Cosmos DB endpoint | *(required)* |
| `AZURE_STORAGE_ACCOUNT_NAME` | Storage account name | *(required)* |
| `FOUNDRY_MODEL_DEPLOYMENT` | Model deployment name | `gpt-4o` |
| `EMBEDDING_MODEL` | Embedding model name | `text-embedding-3-small` |
| `EMBEDDING_DIMENSIONS` | Embedding vector size | `1536` |
| `LLM_TEMPERATURE` | LLM temperature | `0.2` |
| `CHUNKER_MAX_TOKENS` | Max tokens per chunk | `8000` |

## Key Metrics

| Metric | Target |
|--------|--------|
| Review time reduction | ≥ 60% |
| Extraction accuracy | ≥ 95% |
| Pipeline throughput | ≥ 50 docs/hour |
| Client deployment time | ≤ 30 minutes |

## Observability

DocuMind ships with OpenTelemetry auto-instrumentation. HTTP request spans are exported to App Insights automatically. Per-stage pipeline tracing (ingestion → extraction → analysis → search) is available via `create_pipeline_span()` — see the tracing module at `src/documind/core/tracing.py`.

To view traces: **App Insights → Transaction Search → filter by `POST /documents`**.

## Known Limitations

- **Concurrency** — Uses FastAPI `BackgroundTasks` (~30-40 concurrent docs). For production, add a durable queue (Service Bus / Storage Queue).
- **CORS** — Open (`*`) by default. Restrict to frontend origin in production.
- **Auth** — API key auth available (`AUTH_MODE=api_key`). Wire Azure AD for production.
- **Terraform state** — Local by default. Use remote backend (Azure Storage) for teams.

## License

Proprietary — Internal accelerator for practice use.
