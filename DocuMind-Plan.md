# DocuMind — Intelligent Document Processing Pipeline

## Accelerator Overview

**Target Pain Point:** Manual document review (RFPs, contracts, specs)
**Core Stack:** Azure Document Intelligence + GPT-4o + Cosmos DB Vector Search
**Framework:** Microsoft Agent Framework (Python)
**IaC:** Terraform
**Value Proposition:** ~60% reduction in review time, pluggable into any client engagement

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DocuMind Multi-Agent System               │
├─────────────┬──────────────┬──────────────┬─────────────────┤
│ Ingestion   │ Extraction   │ Analysis     │ Search &        │
│ Agent       │ Agent        │ Agent        │ Retrieval Agent │
│ (Upload/OCR)│ (Doc Intel)  │ (GPT-4o)     │ (Cosmos Vector) │
├─────────────┴──────────────┴──────────────┴─────────────────┤
│              Orchestrator Agent (Workflow Coordinator)        │
├──────────────────────────────────────────────────────────────┤
│              Microsoft Agent Framework (Python)               │
├──────────────────────────────────────────────────────────────┤
│  Azure Blob  │ Azure Doc   │ Azure OpenAI │ Cosmos DB        │
│  Storage     │ Intelligence│ (GPT-4o)     │ (Vector Search)  │
└──────────────┴─────────────┴──────────────┴──────────────────┘
```

---

## Agents & Responsibilities

| Agent | Role | Azure Service |
|-------|------|---------------|
| **Orchestrator** | Routes documents through pipeline, manages workflow state | Microsoft Agent Framework Workflow |
| **Ingestion Agent** | Accepts uploads (PDF, DOCX, images), classifies doc type, stores in blob | Azure Blob Storage |
| **Extraction Agent** | OCR, layout analysis, table/key-value extraction | Azure Document Intelligence |
| **Analysis Agent** | Summarization, clause extraction, risk identification, compliance checks | Azure OpenAI (GPT-4o) |
| **Search & Retrieval Agent** | Indexes extracted content, handles semantic/vector search queries | Cosmos DB Vector Search (replaced AI Search to reduce cost — see DocuMind-Cost-Analysis.md) |

---

## Task Plan (Phased)

### Phase 0 — Foundation & Infrastructure (Weeks 1–2)

| # | Task | Details | Owner | Status |
|---|------|---------|-------|--------|
| 0.1 | Define accelerator scope & doc types | Finalize target doc types (RFPs, contracts, specs). Build pluggable doc-type system. | Architect | ✅ |
| 0.1.1 | Create DocumentType config schema | Pydantic schema in `src/documind/doctypes/schema.py` defining doc-type config: name, description, supported formats, extraction fields, analysis prompts path, search index mappings. | Architect | ✅ |
| 0.1.2 | Create per-type YAML configs | YAML config files in `src/documind/doctypes/types/` for RFP, Contract, and Spec. Each defines extraction fields, prompt references, and output mappings. Extensible — add new types by dropping a YAML file. | Architect | ✅ |
| 0.1.3 | Create doc-type registry | Registry in `src/documind/doctypes/registry.py` that auto-discovers YAML configs at startup, validates against schema, and provides lookup by type name. | Architect | ✅ |
| 0.1.4 | Create base extraction/analysis models | Base Pydantic models in `src/documind/core/models/base.py` — `ExtractionResult`, `AnalysisResult`, `RiskItem`, `KeyValuePair` with common fields. | Architect | ✅ |
| 0.1.5 | Create per-type Pydantic models | Type-specific models in `src/documind/core/models/` — `rfp.py`, `contract.py`, `spec.py` inheriting from base, adding type-specific fields. | Architect | ✅ |
| 0.1.6 | Write analysis prompt templates | Populate prompt templates in `src/documind/agents/analysis/prompts/` for all 3 doc types with Jinja2-compatible placeholders. | AI/ML Dev | ✅ |
| 0.2 | Provision Azure resource group | `rg-documind-dev` in eastus2 with standardized tags (environment, project, team, accelerator, managed_by). | DevOps | ✅ |
| 0.3 | Provision Azure AI Services | AI Services account `documind-dev-aoai` with GPT-4o (v2024-11-20, 30K TPM) and text-embedding-3-small deployments. | DevOps | ✅ |
| 0.4 | Provision Azure Document Intelligence | `documind-dev-di` — S0 tier for prebuilt + custom models. | DevOps | ✅ |
| 0.5 | ~~Provision Azure AI Search~~ | ~~Create AI Search service~~ — **Deferred:** Terraform module retained (gated by `enable_ai_search = false`) for future high-volume/hybrid search upgrade. Currently using Cosmos DB vector search (serverless) to avoid ~$250/month fixed cost. | DevOps | Deferred |
| 0.6 | Provision Azure Blob Storage | `documinddevst` — Standard/LRS with containers: `raw-documents`, `processed`, `metadata`. 7-day soft delete. | DevOps | ✅ |
| 0.7 | Provision Azure Cosmos DB | `documind-dev-cosmos` — Serverless, database `documind` with containers: `documents`, `pipeline-state`, `audit-trail`. Vector search via DiskANN. | DevOps | ✅ |
| 0.8 | Provision Azure Key Vault | `documind-dev-kv` — RBAC-enabled, standard tier. | DevOps | ✅ |
| 0.9 | Provision Monitoring | `documind-dev-law` (Log Analytics) + `documind-dev-appi` (App Insights) — OTEL export target. | DevOps | ✅ |
| 0.10 | Set up IaC (Terraform) | 7 Terraform modules (resource_group, ai_services, document_intelligence, storage, cosmos_db, keyvault, monitoring). Local state for dev, `enable_ai_search`/`enable_container_apps` feature flags. 17 resources, all provisioned. | DevOps | ✅ |

---

### Phase 1 — Agent Scaffolding (Weeks 2–3)

| # | Task | Details | Owner | Status |
|---|------|---------|-------|--------|
| 1.1 | Scaffold project | Initialize Python project with `pyproject.toml`, install `agent-framework-azure-ai --pre`. Set up virtual environment and project structure. | Backend Dev | ✅ |
| 1.2 | Build Ingestion Agent | File upload handler, document type classifier (PDF/DOCX/image), blob storage writer. Function tools: `UploadDocument`, `ClassifyDocType`, `StoreToBlobAsync`. | Backend Dev | ✅ |
| 1.3 | Build Extraction Agent | Integrate Azure Document Intelligence SDK. Function tools: `ExtractLayout`, `ExtractKeyValuePairs`, `ExtractTables`. Support prebuilt models (invoice, receipt, contract) + custom models. | Backend Dev | ✅ |
| 1.4 | Build Analysis Agent | GPT-4o powered. Function tools: `SummarizeDocument`, `ExtractClauses`, `IdentifyRisks`, `CheckCompliance`. Prompt engineering for each doc type. | AI/ML Dev | ✅ |
| 1.5 | Build Search & Retrieval Agent | Search integration (Cosmos DB vector search). Function tools: `IndexDocument`, `SemanticSearch`, `FacetedSearch`. Vector indexing via DiskANN. | Backend Dev | ✅ |
| 1.6 | Build Orchestrator Agent | Sequential workflow: Ingest → Extract → Analyze → Index. Error handling, retry policies, status tracking via Cosmos DB. | Backend Dev | ✅ |

---

### Phase 2 — Pipeline Integration (Weeks 3–4)

| # | Task | Details | Owner | Status |
|---|------|---------|-------|--------|
| 2.1 | Wire multi-agent workflow | Use Microsoft Agent Framework Python sequential/handoff workflows to connect all agents. Define shared state for document context passing. | Backend Dev | ✅ |
| 2.2 | Build chunking strategy | Implement intelligent chunking (section-aware, table-preserving) for large documents before GPT-4o analysis. | AI/ML Dev | ✅ |
| 2.3 | Build Cosmos DB vector index | Define Cosmos DB container with vector embedding policy (DiskANN), composite indexes for filtering, and full-text search fields: content, doc_type, clauses, risks, key_values. | Backend Dev | ✅ |
| 2.4 | Migrate SearchService to Cosmos DB | Replace AI Search SDK calls with Cosmos DB vector search API. Implement `VectorSearchQuery` for semantic similarity, filtered queries for faceted search. Enrichment pipeline handled by orchestrator (no external skillset needed). | Backend Dev | ✅ |
| 2.5 | Implement structured output | Define response schemas (JSON) for each agent: `ExtractionResult`, `AnalysisResult`, `RiskAssessment`. | Backend Dev | ✅ |
| 2.6 | Add OpenTelemetry tracing | Instrument all agents with OTEL for latency tracking, error correlation, and pipeline observability via App Insights. | Backend Dev | ✅ |

---

### Phase 3 — API & Client Interface (Weeks 4–5)

**Pre-conditions met:** FastAPI/uvicorn/websockets/python-multipart already in `pyproject.toml`. `api/` and `api/endpoints/` directories scaffolded (empty). `core/tracing.py` has `configure_telemetry()` and `@traced` decorator ready. `core/config/settings.py` reads all Azure endpoints from env vars. All services injectable. `.env` populated from Terraform outputs.

| # | Task | Details | Owner | Status |
|---|------|---------|-------|--------|
| 3.1 | Build FastAPI app factory + OTEL wiring | Create `src/documind/api/main.py` with `create_app()` factory. Lifespan hooks: call `configure_telemetry()` on startup, close service connections on shutdown. Wire `opentelemetry-instrumentation-fastapi` auto-instrumentation (package already installed). Add CORS middleware, global exception handlers returning structured `{error, detail, request_id}` JSON. Dockerfile entrypoint: `documind.api.main:app`. | Backend Dev | ☐ |
| 3.2 | Build API request/response schemas | Create `src/documind/api/schemas.py` — API-layer DTOs wrapping internal models. `UploadRequest` (multipart file + doc_type), `DocumentStatusResponse`, `AnalysisResponse`, `SearchRequest`/`SearchResponse` with pagination. Separate from `core/models/` to decouple API contract from internals. Structured error response model. | Backend Dev | ☐ |
| 3.3 | Build REST API endpoints | **`src/documind/api/endpoints/documents.py`**: `POST /documents` (upload + trigger pipeline), `GET /documents/{id}/status`, `GET /documents/{id}/analysis`. **`src/documind/api/endpoints/search.py`**: `POST /search` (semantic + faceted, uses `VectorSearchService`). Wire to `DocumentPipeline` orchestrator. Background task processing via FastAPI `BackgroundTasks`. | Backend Dev | ☐ |
| 3.4 | Add health & readiness probes | `GET /health` (liveness — returns 200 immediately), `GET /ready` (checks Cosmos DB `documind-dev-cosmos`, Blob Storage `documinddevst`, OpenAI `documind-dev-aoai` connectivity). Required by Container Apps for zero-downtime deployments. Add to `src/documind/api/endpoints/health.py`. | Backend Dev | ☐ |
| 3.5 | Build real-time status updates | WebSocket endpoint `WS /documents/{id}/ws` for live pipeline progress (stage transitions, completion). SSE fallback `GET /documents/{id}/events` for corporate proxy environments. Add to `src/documind/api/endpoints/events.py`. Reads status from Cosmos DB `pipeline-state` container. | Backend Dev | ☐ |
| 3.6 | Implement authentication | **3.6a** API key auth via `X-API-Key` header (FastAPI `Security` dependency, key stored in Key Vault `documind-dev-kv`) for dev/demo. **3.6b** Azure Entra ID bearer token validation for production (via `azure-identity`). Auth middleware in `src/documind/api/auth.py` with configurable mode via `AUTH_MODE` env var. | Backend Dev | ☐ |
| 3.7 | Write API tests | Unit tests for all endpoints (mock services), test auth middleware, test error handling, test health probes. Target: match existing test patterns in `tests/conftest.py` (MagicMock services, pytest-asyncio). Use `httpx.AsyncClient` with FastAPI `TestClient`. Add `tests/test_api.py` and `tests/test_api_auth.py`. | Backend Dev | ☐ |

---

### Phase 4 — Quality, Evaluation & Hardening (Weeks 5–6)

| # | Task | Details | Owner | Status |
|---|------|---------|-------|--------|
| 4.1 | Build evaluation dataset | Curate 50+ annotated documents with ground-truth extractions, summaries, and risk labels. | AI/ML Dev | ☐ |
| 4.2 | Implement batch evaluation | Use Foundry eval tooling to measure: extraction accuracy, summary quality (ROUGE/BERTScore), risk detection precision/recall. | AI/ML Dev | ☐ |
| 4.3 | Prompt optimization | Use Foundry prompt optimizer for Analysis Agent prompts per doc type. | AI/ML Dev | ☐ |
| 4.4 | Error handling & resilience | Retry policies, dead-letter queues, graceful degradation when services are unavailable. | Backend Dev | ☐ |
| 4.5 | Security hardening | Input validation, content safety filters, PII redaction pipeline, private endpoints for all Azure services. | Security | ☐ |
| 4.6 | Load testing | Test with 100+ concurrent documents, measure throughput, identify bottlenecks. | QA | ☐ |

---

### Phase 5 — Packaging as Accelerator (Weeks 6–7)

| # | Task | Details | Owner | Status |
|---|------|---------|-------|--------|
| 5.1 | Parameterize for pluggability | Environment-specific configs, doc type schemas as plug-in configs, custom model registry. | Architect | ☐ |
| 5.2 | Create deployment automation | `azd` template with `azure.yaml`, one-command provisioning + deployment. | DevOps | ☐ |
| 5.3 | Write accelerator documentation | Architecture guide, setup guide, customization guide, doc-type extension guide. | Tech Writer | ☐ |
| 5.4 | Build sample document packs | Sample RFPs, contracts, specs with expected outputs for client demos. | AI/ML Dev | ☐ |
| 5.5 | Build review dashboard (optional) | Lightweight Streamlit/Gradio demo UI for client presentations. Upload, status, results viewer. Not production UI — clients integrate via API. | Frontend Dev | ☐ |
| 5.6 | Create onboarding runbook | Step-by-step client engagement playbook: fork → configure → deploy → customize. | Architect | ☐ |

---

## Azure Services Summary

| Service | Purpose | Recommended SKU |
|---------|---------|-----------------|
| Azure AI Foundry | Agent hosting, model catalog, evaluation | Standard |
| Azure OpenAI (GPT-4o) | Analysis, summarization, reasoning | Pay-as-you-go |
| Azure Document Intelligence | OCR, layout, key-value, table extraction | S0 |
| Azure AI Search | ~~Semantic search, vector index, skillsets~~ — deferred (`enable_ai_search = false`). Cosmos DB vector search used instead. | Standard (when enabled) |
| Azure Blob Storage | Raw & processed document storage | StorageV2 / Hot |
| Azure Cosmos DB | Pipeline state, metadata, audit trail, **vector search** | Serverless |
| Azure Key Vault | Secrets, connection strings | Standard |
| Azure Monitor + App Insights | Observability, tracing, dashboards | Pay-as-you-go |
| Azure Container Apps / App Service | API hosting | Consumption / S1 |

---

## Key Design Decisions

1. **Multi-Agent over Monolith** — Each processing stage is an independent agent, enabling parallel development, isolated testing, and independent scaling.
2. **Microsoft Agent Framework (Python)** — Provides built-in workflow orchestration (sequential, handoff, concurrent), OpenTelemetry tracing, and Foundry integration. Python chosen for faster prototyping, richer AI ecosystem, and broader developer availability.
3. **Document Intelligence Prebuilt + Custom** — Start with prebuilt models for speed; add custom models per client for domain-specific docs.
4. **Hybrid Search (Keyword + Vector)** — Cosmos DB DiskANN vector search for semantic similarity, SQL queries for keyword/faceted search. Azure AI Search module retained in Terraform (gated by `enable_ai_search`) for future upgrade path when high-volume hybrid search is needed.
5. **IaC-First** — All infrastructure codified in Terraform for repeatable, one-click client deployments.
6. **Pluggable Doc Types** — New document types added via configuration (schema + prompts), no code changes required.

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| GPT-4o rate limits on large batches | Pipeline stalls | Implement queue-based throttling, batch sizing, retry with exponential backoff |
| Document Intelligence accuracy on poor scans | Low extraction quality | Pre-processing (deskew, contrast), fallback to GPT-4o vision for difficult pages |
| Large document token limits | Incomplete analysis | Intelligent chunking with overlap, map-reduce summarization pattern |
| Data residency / compliance | Client rejection | Deploy in client-approved Azure region, private endpoints, customer-managed keys |
| Cost overruns on high-volume processing | Budget exceeded | Implement cost tracking per document, tier-based processing (fast vs. thorough) |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Document review time reduction | ≥ 60% vs. manual baseline |
| Extraction accuracy (key-value pairs) | ≥ 95% on supported doc types |
| Search relevance (NDCG@10) | ≥ 0.85 |
| Pipeline throughput | ≥ 50 documents/hour |
| Time to deploy for new client | ≤ 2 hours (with `azd up`) |
| Onboarding new doc type | ≤ 1 day (config + prompt tuning) |

---

## Accelerator Enhancements

Post-MVP enhancements to make DocuMind production-grade and multi-cloud
ready. Executed in five phases — each phase builds on the previous one.
Current target cloud is **Azure**; multi-cloud support is additive (no
Azure code is replaced, only abstracted behind protocols).

### Enhancement Phase 1 — Task Registry

**Problem:** The `_TASK_DISPATCH` dict in `agents/analysis/agent.py` is
hardcoded. Adding a new analysis task (e.g. `identify_risks`,
`extract_entities`) requires a code change to the agent.

**Solution:** A `@register_task` decorator and a `TaskRegistry` singleton
that auto-collects task functions at import time.

| # | Task | Details | Status |
|---|------|---------|--------|
| E1.1 | Create `TaskRegistry` class | New file `src/documind/agents/analysis/task_registry.py`. Singleton registry with `register(name, fn)`, `get(name)`, `list_all()` methods and a `@register_task(name)` decorator. | ☐ |
| E1.2 | Decorate existing tool functions | Add `@register_task("summarize")`, `@register_task("extract_clauses")`, `@register_task("compliance_check")` to the existing functions in `agents/analysis/tools/tools.py`. No signature changes. | ☐ |
| E1.3 | Replace `_TASK_DISPATCH` in agent | Update `agents/analysis/agent.py` to use `TaskRegistry.get(task.name)` instead of the hardcoded dict. Remove the `_TASK_DISPATCH` variable. | ☐ |
| E1.4 | Trigger registration at import | Update `agents/analysis/__init__.py` to import the tools module so decorators execute at startup. | ☐ |

**Test impact:** None — existing 140 tests pass unchanged. `_TASK_DISPATCH` is never imported or mocked in tests.

---

### Enhancement Phase 2 — Service Protocols (Multi-Cloud)

**Problem:** Service classes are concrete Azure implementations. Swapping
to AWS (S3, Textract, Bedrock) or GCP (Cloud Storage, Document AI, Vertex)
requires rewriting agents.

**Solution:** Define `typing.Protocol` contracts. Azure services already
satisfy them structurally — no refactoring needed, just explicit interface
declaration.

| # | Task | Details | Status |
|---|------|---------|--------|
| E2.1 | Define service protocols | New file `src/documind/core/protocols.py` with `StorageProtocol`, `DocumentExtractorProtocol`, `LLMProtocol`, `SearchProtocol`, `StateStoreProtocol`. | ☐ |
| E2.2 | Update orchestrator type hints | Change `DocumentPipeline` constructor hints from concrete classes to protocols. Runtime behaviour unchanged. | ☐ |
| E2.3 | Update executor type hints | Change `ExtractionExecutor`, `SearchExecutor` constructor hints to use protocols. | ☐ |

**Multi-cloud approach:**

```
src/documind/services/
├── blob_storage.py           ← Azure (implements StorageProtocol) — DEFAULT
├── document_intelligence.py  ← Azure (implements DocumentExtractorProtocol) — DEFAULT
├── vector_search.py          ← Azure (implements SearchProtocol) — DEFAULT
├── cosmos.py                 ← Azure (implements StateStoreProtocol) — DEFAULT
│
│  Future — clients add per engagement, no core changes:
├── s3_storage.py             ← AWS (implements StorageProtocol)
├── textract.py               ← AWS (implements DocumentExtractorProtocol)
└── opensearch.py             ← AWS (implements SearchProtocol)
```

**Test impact:** None — `typing.Protocol` is structural, not nominal.

---

### Enhancement Phase 3 — MCP Server

**Problem:** DocuMind analysis capabilities are only accessible via the
full REST pipeline (upload → ingest → extract → analyze → index). AI
agents (Copilot, Claude Desktop, custom agents) can't call individual
analysis tools directly.

**Solution:** An MCP (Model Context Protocol) server that exposes analysis
tool functions as MCP tools. Standalone process — requires only an LLM
backend, no blob storage or Cosmos DB.

**Scope: Analysis tools only.** Ingestion, extraction, and search are
pipeline concerns that need file bytes and infrastructure — they don't
fit the MCP "send text, get result" pattern.

| # | Task | Details | Status |
|---|------|---------|--------|
| E3.1 | Install MCP SDK | Add `mcp>=1.0.0` to `pyproject.toml` dependencies. | ☐ |
| E3.2 | Build MCP server | New file `src/documind/mcp/server.py`. Register tools from `TaskRegistry`, wire `LLMProtocol` for LLM calls, expose `list_doc_types()` as metadata tool. | ☐ |
| E3.3 | Add prompts as MCP resources | Expose prompt templates as `prompts://{doc_type}/{task}` resources so MCP clients can inspect available prompts. | ☐ |
| E3.4 | Add entry point | Add `[project.scripts] documind-mcp = "documind.mcp.server:main"` to `pyproject.toml`. | ☐ |
| E3.5 | Write MCP server tests | New `tests/test_mcp_server.py` — test tool registration, invocation with mock LLM, error handling. | ☐ |

**MCP tools exposed:**

| Tool | Input | Output |
|------|-------|--------|
| `summarize_document` | `text`, `doc_type?` | `{summary, risks[], key_findings[]}` |
| `extract_clauses` | `text` | `{clauses[], risk_ratings[], obligations[]}` |
| `check_compliance` | `text` | `{compliance_score, gaps[], recommendations[]}` |
| `list_doc_types` | — | `{types: [{name, description, tasks}]}` |

**Optional (when search infra is configured):**

| Tool | Input | Output |
|------|-------|--------|
| `search_documents` | `query`, `top?` | `{results: [{id, score, snippet}]}` |

**Why not all agents as MCP?**

| Agent | MCP? | Reason |
|-------|------|--------|
| Analysis | **Yes** | Stateless — text in, JSON out. No infra needed beyond LLM. |
| Ingestion | No | Needs blob storage + file bytes. MCP clients send text, not files. |
| Extraction | No | Needs Document Intelligence + raw file bytes. MCP clients already have text. |
| Search | Optional | Query-only search could work, but couples MCP server to Cosmos DB infra. Offered as opt-in. |

**Test impact:** New `tests/test_mcp_server.py` only — no changes to existing tests.

---

### Enhancement Phase 4 — Scaffold Script

**Problem:** Adding a new document type requires manually creating 3–4
files (YAML config, prompt template, model, test stub) in the right
directories.

**Solution:** A single command that generates all files from templates.

| # | Task | Details | Status |
|---|------|---------|--------|
| E4.1 | Build scaffold script | New file `scripts/add_doctype.py`. Takes a doc-type name, generates YAML config, prompt template stub, and test stub. | ☐ |

**Usage:**

```bash
python scripts/add_doctype.py invoice

Created:
  src/documind/doctypes/types/invoice.yaml
  src/documind/agents/analysis/prompts/invoice-summary.txt
  tests/test_doctype_invoice.py
```

**Test impact:** New `tests/test_add_doctype.py` only.

---

### Enhancement Phase 5 — Developer Experience

**Problem:** Onboarding requires reading README, running multiple commands,
and knowing which settings are hardcoded vs configurable.

**Solution:** Makefile for common workflows + config-driven settings for
currently-hardcoded values.

| # | Task | Details | Status |
|---|------|---------|--------|
| E5.1 | Create Makefile | Targets: `setup`, `test`, `run`, `mcp-server`, `add-doctype`, `lint`, `docker-build`. | ☐ |
| E5.2 | Make chunking config-driven | Move `max_tokens=8000` and `EMBEDDING_DIMENSIONS=1536` from hardcoded values to `settings.py`. | ☐ |

**Test impact:** `test_chunker.py` may need a minor fixture update if it asserts on specific chunk sizes.

---

### Enhancement Execution Order & Dependencies

```
Phase 1: Task Registry
    │
    ├──▶ Phase 2: Service Protocols  (independent, can parallel with Phase 1)
    │
    ├──▶ Phase 3: MCP Server         (depends on Phase 1 — uses TaskRegistry)
    │
    ├──▶ Phase 4: Scaffold Script    (depends on Phase 1 — generates @register_task code)
    │
    └──▶ Phase 5: Makefile + Config  (independent, can be done anytime)
```

### Files Created / Modified

| Action | File | Phase |
|--------|------|-------|
| **New** | `src/documind/agents/analysis/task_registry.py` | 1 |
| **Edit** | `src/documind/agents/analysis/tools/tools.py` | 1 |
| **Edit** | `src/documind/agents/analysis/agent.py` | 1 |
| **Edit** | `src/documind/agents/analysis/__init__.py` | 1 |
| **New** | `src/documind/core/protocols.py` | 2 |
| **Edit** | `src/documind/agents/orchestrator/workflow.py` | 2 |
| **Edit** | `src/documind/agents/extraction/agent.py` | 2 |
| **Edit** | `src/documind/agents/search/agent.py` | 2 |
| **New** | `src/documind/mcp/__init__.py` | 3 |
| **New** | `src/documind/mcp/server.py` | 3 |
| **Edit** | `pyproject.toml` | 3 |
| **New** | `scripts/add_doctype.py` | 4 |
| **New** | `Makefile` | 5 |
| **Edit** | `src/documind/core/config/settings.py` | 5 |
| **Edit** | `src/documind/services/chunker.py` | 5 |

### New Test Files

| File | Phase | Tests |
|------|-------|-------|
| `tests/test_task_registry.py` | 1 | Registry CRUD, decorator, duplicate handling |
| `tests/test_mcp_server.py` | 3 | Tool invocation, mock LLM, error paths |
| `tests/test_add_doctype.py` | 4 | File generation, overwrite protection |
