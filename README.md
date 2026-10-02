# DocuMind — Intelligent Document Processing Pipeline

> Multi-Agent AI Accelerator for RFPs, Contracts & Specifications

## Overview

DocuMind is a reusable practice accelerator that automates document review using a multi-agent AI pipeline. It targets the pain of manual document review across client engagements — RFPs, contracts, and technical specifications — delivering ~60% reduction in review time.

It can run in three modes with **no code changes** — picked by env vars:

| Mode | LLM | Vectors / Metadata / Blobs | Best for |
|------|-----|----------------------------|----------|
| **Azure** | Azure OpenAI (GPT-4o) | Cosmos DB + Blob Storage + Document Intelligence | Production, clients |
| **Offline + Gemini** | Google Gemini (cloud) | ChromaDB + SQLite + local filesystem | Fast local dev, demos |
| **Offline + Ollama** | Ollama (local, llama3.x) | ChromaDB + SQLite + local filesystem | Fully air‑gapped runs |

### Key Features

- **Multi-agent pipeline** — Ingestion → Extraction → Analysis → Search, orchestrated end-to-end
- **RAG Q&A** — `POST /ask` grounds LLM answers in the indexed corpus with inline `[n]` citations
- **Pluggable document types** — Add new doc types via YAML config, no code changes
- **MCP server** — Expose analysis tools at `/mcp` for AI assistants (Copilot, Claude, etc.)
- **React SPA frontend** — Upload, track progress, view results, semantic search, and ask questions
- **One-command Azure deploy** — `azd up` provisions all Azure infra, builds & pushes container
- **Managed identity everywhere** — Zero secrets in Azure mode; all services use RBAC

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

Pick one of the three modes below. All three share the same code — the backend is selected by the `BACKEND` and `LOCAL_LLM_PROVIDER` env vars.

### Prerequisites (common to all modes)

- **Python 3.11+**
- **Node.js 18+** (for the web UI)
- **Git**

Mode-specific extras are listed in each section below.

---

### Mode A — Azure (production / client deployments)

Full managed Azure stack with Azure OpenAI, Document Intelligence, Cosmos DB (vector), Blob Storage, and Container Apps.

**Extra prerequisites**

- [Azure Developer CLI (`azd`)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- [Terraform ≥ 1.6](https://www.terraform.io/downloads)
- [Docker](https://docs.docker.com/get-docker/)
- An Azure subscription with Azure OpenAI access

**One-command deploy**

```powershell
azd auth login
azd up
```

This provisions all Azure resources (Terraform), builds the Docker image, pushes it to ACR, and deploys to Container Apps. The API URL is printed at the end.

**Local run against Azure services**

```powershell
make install
cd web; npm install; cd ..

# Generate .env from the Terraform outputs you just created
make env-gen

# Start API (port 8000) + frontend (port 3000)
make dev
```

Minimum env for Mode A (filled in automatically by `make env-gen`):

```env
BACKEND=azure
AUTH_MODE=entra_id         # or api_key / none
AZURE_OPENAI_ENDPOINT=https://<...>.openai.azure.com
AZURE_OPENAI_KEY=           # leave blank to use managed identity
AZURE_DOC_INTELLIGENCE_ENDPOINT=https://<...>.cognitiveservices.azure.com
AZURE_COSMOS_ENDPOINT=https://<...>.documents.azure.com:443/
AZURE_STORAGE_ACCOUNT_NAME=<...>
FOUNDRY_MODEL_DEPLOYMENT=gpt-4o
EMBEDDING_MODEL=text-embedding-3-small
```

---

### Mode B — Offline + Gemini (recommended for local dev)

Runs the full pipeline locally against ChromaDB + SQLite + local filesystem, with **Google Gemini** as the LLM (fast, no local GPU required). Embeddings use `sentence-transformers/all-MiniLM-L6-v2` (CPU, ~90 MB, downloads once).

**Extra prerequisites**

- A Gemini API key — [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)

**Install**

```powershell
# Windows PowerShell
make install-offline
cd web; npm install; cd ..
```

**Configure**

```powershell
Copy-Item .env.local.template .env
```

Edit `.env` to select Gemini and add your key:

```env
BACKEND=local
AUTH_MODE=none

LOCAL_LLM_PROVIDER=gemini
GEMINI_API_KEY=<your-key>
GEMINI_MODEL=gemini-3.5-flash
GEMINI_TIMEOUT_SECONDS=120
GEMINI_MAX_OUTPUT_TOKENS=2048

# Vectors / metadata / blobs — all local
CHROMA_PATH=./data/chroma
SQLITE_PATH=./data/documind.sqlite
LOCAL_BLOB_DIR=./data/blobs
LOCAL_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

**Run**

```powershell
make dev-offline
```

- API: http://localhost:8000  (`/docs` for OpenAPI, `/ready` for health)
- Web: http://localhost:3000

`/ready` should report `gemini: ok, model=gemini-3.5-flash`.

---

### Mode C — Offline + Ollama (fully air‑gapped)

Everything from Mode B, but swaps Gemini for a locally hosted Ollama model — **no outbound network calls** after the model is pulled.

**Extra prerequisites**

- [Ollama](https://ollama.com/download) running locally
- A pulled chat model, e.g. `ollama pull llama3.2:3b` (small/fast) or `ollama pull llama3.1:8b` (better quality)

**Install**

```powershell
make install-offline
cd web; npm install; cd ..
ollama pull llama3.2:3b
```

**Configure**

```powershell
Copy-Item .env.local.template .env
```

Edit `.env` to select Ollama:

```env
BACKEND=local
AUTH_MODE=none

LOCAL_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_TIMEOUT_SECONDS=900
OLLAMA_NUM_PREDICT=2048
LLM_TEMPERATURE=0.1

CHROMA_PATH=./data/chroma
SQLITE_PATH=./data/documind.sqlite
LOCAL_BLOB_DIR=./data/blobs
LOCAL_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

**Run**

```powershell
# Make sure Ollama is running first (ollama serve, or the tray app)
make dev-offline
```

`/ready` should report `ollama: ok`.

> **Note.** Ollama on CPU is noticeably slower than Gemini (minutes vs seconds per document). Use Mode B for interactive work and Mode C when you need an air‑gapped run.

---

### Smoke test (works in all modes)

Two sample files are included at the repo root for a 60-second demo:

- [sample-contract.txt](sample-contract.txt) — Professional Services Agreement
- [sample-rfp.txt](sample-rfp.txt) — Cloud Migration RFP

```powershell
# Upload the sample contract
$upload = Invoke-RestMethod -Uri "http://127.0.0.1:8000/documents" -Method Post `
    -Form @{ file = Get-Item sample-contract.txt; doc_type = "auto" }
$id = $upload.document_id

# Poll status (repeat until status = "completed")
Invoke-RestMethod -Uri "http://127.0.0.1:8000/documents/$id"

# Ask a grounded question (RAG)
Invoke-RestMethod -Uri "http://127.0.0.1:8000/ask" -Method Post `
    -ContentType "application/json" `
    -Body (@{ question = "Who are the parties in the agreement?"; doc_type = "contract"; top = 3 } | ConvertTo-Json)
```

Or just open http://localhost:3000 and use the **Upload**, **Search**, and **Ask** tabs.

---

### Switching modes

There is no re-install step. Change the env vars and restart:

| From → To | Change |
|-----------|--------|
| Azure → Offline+Gemini | `BACKEND=local`, `LOCAL_LLM_PROVIDER=gemini`, set `GEMINI_API_KEY` |
| Offline+Gemini → Offline+Ollama | `LOCAL_LLM_PROVIDER=ollama`, ensure Ollama is running |
| Offline → Azure | `BACKEND=azure`, fill in the Azure endpoints |

Delete `./data/` to reset the offline install (vectors, SQLite, blobs).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Liveness check |
| `GET`  | `/ready` | Readiness probe (verifies LLM + vector store + metadata store) |
| `POST` | `/documents` | Upload a document for processing |
| `GET`  | `/documents/{id}` | Current status + metadata |
| `GET`  | `/documents/{id}/analysis` | Full extraction + analysis results |
| `POST` | `/search` | Semantic search across the indexed corpus |
| `POST` | `/ask` | **RAG Q&A** — grounded answer with `[n]` citations |
| `GET`  | `/events/{id}` | SSE stream of real-time pipeline updates |
| `*`    | `/mcp` | MCP endpoint (Streamable HTTP) |

Interactive OpenAPI UI: http://localhost:8000/docs

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
make install          Install dependencies (Azure/base + dev extras)
make install-offline  Install dependencies for offline mode (adds Chroma + Ollama HTTP + local extractors)
make dev              API + frontend in parallel (uses current .env)
make dev-offline      API + frontend with BACKEND=local (offline mode)
make run              API server only (port 8000)
make test             Run unit tests
make lint             Run ruff linter
make format           Auto-format code
make deploy           Full Azure deployment (azd up)
make provision        Provision Azure infra only
make docker-build     Build Docker image
make docker-push      Build + push to ACR
make infra-init       Terraform init
make infra-plan       Terraform plan (dev)
make infra-apply      Terraform apply (dev)
make env-gen          Generate .env from Terraform outputs
make mcp-http         API + MCP server (Streamable HTTP at /mcp)
make web-install      Install frontend dependencies
make web-dev          Vite dev server (port 3000)
make web-build        Build frontend for production
make add-doctype      Scaffold a new doc type
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

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `/ready` shows `gemini: error` | `GEMINI_API_KEY` not set, invalid, or the chosen `GEMINI_MODEL` isn't available in your region. Try `gemini-3.5-flash`. |
| `/ready` shows `ollama: error` | Ollama not running. Run `ollama serve` (or launch the tray app) and `ollama pull <OLLAMA_MODEL>`. |
| First document upload takes 30–60 s | Sentence-transformers model download — one-time, cached under `~/.cache/huggingface/`. |
| `/ask` returns *"The provided documents do not contain enough information…"* | Expected when retrieval misses — try increasing `top`, or rephrase the question. |
| PDF extraction returns empty content | Image-only PDF. Offline mode has no OCR; use Mode A (Azure Document Intelligence) for scanned PDFs. |
| `sqlite3.OperationalError: database is locked` | Multiple writers hit SQLite at once. Restart the API. |
| `429 / 503` from Gemini | Rate limited or model unavailable. The client retries with exponential backoff; keep upload rates modest. |
| Frontend 404s against `/ask` | Vite proxy out of date — restart `make web-dev`. |

See [RUNNING-OFFLINE.md](RUNNING-OFFLINE.md) for the deep-dive on offline mode.

## Known Limitations

- **Concurrency** — Uses FastAPI `BackgroundTasks` (~30-40 concurrent docs). For production, add a durable queue (Service Bus / Storage Queue).
- **CORS** — Open (`*`) by default. Restrict to frontend origin in production.
- **Auth** — API key auth available (`AUTH_MODE=api_key`). Wire Azure AD for production.
- **Terraform state** — Local by default. Use remote backend (Azure Storage) for teams.

## License

Proprietary — Internal accelerator for practice use.
