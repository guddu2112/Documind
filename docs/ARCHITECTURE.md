# DocuMind — Architecture & Flow Document

> **Intelligent Document Processing Pipeline**
> EPAM Practice Accelerator · Azure AI Platform · Python

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview](#2-system-overview)
3. [Multi-Agent Pipeline Architecture](#3-multi-agent-pipeline-architecture)
4. [Step-by-Step Processing Flow](#4-step-by-step-processing-flow)
5. [Agent Details & Tools](#5-agent-details--tools)
6. [Azure Services & Resource Map](#6-azure-services--resource-map)
7. [Data Models & State Machine](#7-data-models--state-machine)
8. [API Layer](#8-api-layer)
9. [Pluggable Document Types](#9-pluggable-document-types)
10. [Observability & Telemetry](#10-observability--telemetry)
11. [Azure Deployment Architecture](#11-azure-deployment-architecture)
12. [Production Networking & Security](#12-production-networking--security)
13. [Infrastructure as Code](#13-infrastructure-as-code)
14. [Scalability & Performance](#14-scalability--performance)

---

## 1. Executive Summary

DocuMind is an **AI-powered document processing accelerator** that ingests enterprise documents (RFPs, contracts, technical specs), extracts structured data using Azure Document Intelligence, runs LLM-based analysis via GPT-4o, and indexes results for semantic search — all orchestrated through a **multi-agent pipeline** built on Microsoft Agent Framework.

**Key Metrics:**
| Metric | Target |
|--------|--------|
| Review Time Reduction | ~60% |
| Extraction Accuracy | 95%+ |
| Throughput | 50+ docs/hour |
| Client Deployment | < 2 hours |

---

## 2. System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DocuMind — System Layers                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  CLIENT LAYER                                                    │   │
│  │  React Dashboard · Upload · Status Tracking · Analysis · Search  │   │
│  └───────────────────────────────┬──────────────────────────────────┘   │
│                                  │ HTTP / WebSocket / SSE               │
│  ┌───────────────────────────────▼──────────────────────────────────┐   │
│  │  API LAYER (FastAPI)                                             │   │
│  │  POST /documents · GET /status · GET /analysis · POST /search   │   │
│  │  WS /ws · GET /events · GET /health · GET /ready                │   │
│  └───────────────────────────────┬──────────────────────────────────┘   │
│                                  │                                      │
│  ┌───────────────────────────────▼──────────────────────────────────┐   │
│  │  ORCHESTRATOR AGENT (Microsoft Agent Framework)                  │   │
│  │  Sequential Workflow: Ingest → Extract → Analyze → Index         │   │
│  └──┬──────────┬──────────────┬─────────────┬──────────────────────┘   │
│     │          │              │             │                           │
│  ┌──▼───┐  ┌──▼──────┐  ┌───▼─────┐  ┌───▼──────┐                    │
│  │Ingest│  │Extract  │  │Analyze  │  │Search &  │  ← Specialist      │
│  │Agent │  │Agent    │  │Agent    │  │Index     │    Agents           │
│  └──┬───┘  └──┬──────┘  └───┬─────┘  └───┬──────┘                    │
│     │         │             │             │                            │
│  ┌──▼─────────▼─────────────▼─────────────▼────────────────────────┐  │
│  │  SERVICES LAYER (Azure SDK Wrappers)                            │  │
│  │  BlobStorage · CosmosDB · DocIntelligence · VectorSearch        │  │
│  │  PromptLoader · DocumentChunker                                 │  │
│  └──┬─────────┬─────────────┬─────────────┬───────────────────────┘   │
│     │         │             │             │                            │
│  ┌──▼─────────▼─────────────▼─────────────▼────────────────────────┐  │
│  │  AZURE PLATFORM                                                 │  │
│  │  Blob Storage · Cosmos DB · Doc Intelligence · Azure OpenAI     │  │
│  │  Key Vault · App Insights · Log Analytics                       │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  INFRASTRUCTURE (Terraform + azd)                               │   │
│  │  Modules: resource_group · storage · cosmos_db · ai_services    │   │
│  │  document_intelligence · monitoring · keyvault · container_apps  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Multi-Agent Pipeline Architecture

The core of DocuMind is a **four-stage sequential agent pipeline**. Each agent is a self-contained executor with its own tools, responsible for one phase of document processing.

```
                    ┌──────────────────────────┐
                    │   Document Upload (API)   │
                    │   POST /documents         │
                    └────────────┬─────────────┘
                                 │ file_bytes + filename + doc_type_hint
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (DocumentPipeline)                      │
│                    Microsoft Agent Framework                           │
│                                                                        │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────┐    ┌────────┐  │
│  │  INGESTION  │───▶│  EXTRACTION  │───▶│  ANALYSIS  │───▶│ SEARCH │  │
│  │    Agent    │    │    Agent     │    │   Agent    │    │ Agent  │  │
│  │             │    │              │    │            │    │        │  │
│  │ classify    │    │ OCR / layout │    │ summarize  │    │ index  │  │
│  │ upload blob │    │ tables, KVs  │    │ risks      │    │ embed  │  │
│  │ create rec  │    │ raw text     │    │ clauses    │    │ vector │  │
│  └──────┬──────┘    └──────┬───────┘    └─────┬──────┘    └───┬────┘  │
│         │                  │                  │               │        │
│    Azure Blob         Azure Doc          Azure OpenAI    Cosmos DB    │
│    Storage            Intelligence       (GPT-4o)        DiskANN     │
│                                                          + Embeddings │
│                                                                        │
│  Status:  PENDING ──▶ EXTRACTING ──▶ ANALYZING ──▶ INDEXING ──▶ DONE  │
│                                                                        │
│  State persisted to Cosmos DB (documents container) at each stage      │
└────────────────────────────────────────────────────────────────────────┘
```

**Why Sequential (not parallel)?**

Each stage depends on the output of the previous one:
- Extraction needs the raw file bytes from Ingestion
- Analysis needs the extracted text/tables from Extraction
- Indexing needs both extraction and analysis results

---

## 4. Step-by-Step Processing Flow

### Step 1: Document Upload

```
User ──[HTTP POST multipart/form-data]──▶ FastAPI /documents endpoint
```

1. **Validate** — file exists, not empty, valid extension (PDF, DOCX, XLSX, PPTX, PNG, JPG, TIFF)
2. **Generate UUID** — `document_id = uuid4()`
3. **Create Record** — `DocumentRecord` with status `PENDING` → Cosmos DB `documents` container
4. **Return 202 Accepted** — `{ document_id, filename, doc_type, status: "pending" }`
5. **Queue Background Task** — `BackgroundTasks.add_task(_run_pipeline_background, ...)`

The API returns **immediately**. Processing happens asynchronously.

### Step 2: Ingestion Agent

| Aspect | Detail |
|--------|--------|
| **Executor** | `IngestionExecutor` |
| **Input** | `file_bytes`, `filename`, `doc_type_hint` |
| **Output** | `IngestionOutput(record, file_bytes)` |
| **Azure Service** | Azure Blob Storage |
| **Status** | `PENDING` |

**Actions:**

```
2a. classify_doc_type()
    ├── If doc_type_hint provided → look up in DocTypeRegistry
    ├── Else → match file extension to registered document types
    └── Returns: DocumentTypeConfig (model, fields, tasks, mappings)

2b. upload_document()
    ├── Validate file size and extension
    ├── Create DocumentRecord (PENDING)
    └── Returns: record with document_id

2c. store_to_blob()
    ├── Upload to Azure Blob Storage
    ├── Container: "raw-documents"
    ├── Path: "{document_id}/{filename}"
    └── Set record.blob_url = returned URL
```

### Step 3: Extraction Agent

| Aspect | Detail |
|--------|--------|
| **Executor** | `ExtractionExecutor` |
| **Input** | `IngestionOutput` |
| **Output** | `ExtractionOutput(extraction, ingestion)` |
| **Azure Service** | Azure Document Intelligence |
| **Status** | `EXTRACTING` |

**Actions:**

```
3a. Select DI model from document type config
    ├── "prebuilt-layout"     → RFPs, specs (general)
    ├── "prebuilt-contract"   → contracts & agreements
    ├── "prebuilt-invoice"    → invoices
    └── Custom model ID       → client-trained models

3b. extract_layout(file_bytes, model_id)
    └── DocumentIntelligenceService.analyze_document()
        └── Azure DI SDK: AnalyzeDocument API call

3c. Parse DI response:
    ├── extract_text()            → raw_text (full document text)
    ├── extract_key_value_pairs() → list[KeyValuePair] (form fields)
    ├── extract_tables()          → list[ExtractedTable] (rows, headers)
    └── get_page_count()          → int

3d. build_extraction_result()
    └── Assemble ExtractionResult model with all parsed data
```

**ExtractionResult contains:**
- `page_count`, `extracted_at` timestamp
- `key_value_pairs` — structured form fields with confidence scores
- `tables` — tabular data with headers and rows
- `raw_text` — full text content (used by Analysis agent)
- `confidence_score` — DI model confidence
- `metadata` — additional DI response metadata

### Step 4: Analysis Agent

| Aspect | Detail |
|--------|--------|
| **Executor** | `AnalysisExecutor` |
| **Input** | `ExtractionOutput` |
| **Output** | `AnalysisOutput(analysis, extraction)` |
| **Azure Service** | Azure OpenAI (GPT-4o) |
| **Status** | `ANALYZING` |

**Actions:**

```
4a. Load analysis tasks from document type config
    Example for RFP: [summarize, extract_clauses, compliance_check]

4b. (Optional) Chunk long documents
    └── DocumentChunker splits text at natural boundaries
        ├── Max 8,000 tokens per chunk
        ├── 200 token overlap for context continuity
        └── Preserves table rows and numbered clauses

4c. For EACH analysis task:
    ├── Load Jinja2 prompt template (from prompts/ directory)
    ├── Render template with: document_text, doc_type, extraction data
    ├── Call GPT-4o via Azure OpenAI
    │   ├── Uses structured output (response_format = json_schema)
    │   ├── Schema enforces exact output structure
    │   └── Robust JSON parsing with markdown stripping
    └── Collect task result

4d. build_analysis_result()
    └── Merge all task outputs into AnalysisResult
```

**Analysis task dispatch:**

| Task | Tool Function | Description |
|------|---------------|-------------|
| `summarize` | `summarize_document()` | Executive summary of the document |
| `extract_clauses` | `extract_clauses()` | Key clause extraction (contracts) |
| `compliance_check` | `check_compliance()` | Regulatory/compliance validation |
| `identify_risks` | `identify_risks()` | Risk identification with severity |

**AnalysisResult contains:**
- `summary` — executive summary of the document
- `risks` — `list[RiskItem(title, description, severity, recommendation)]`
- `analyzed_at` timestamp
- `metadata` — task-specific data (clauses, compliance gaps, etc.)

### Step 5: Search & Indexing Agent

| Aspect | Detail |
|--------|--------|
| **Executor** | `SearchExecutor` |
| **Input** | `AnalysisOutput` |
| **Output** | `SearchOutput(document_id, index_result)` |
| **Azure Service** | Azure OpenAI (Embeddings) + Cosmos DB (DiskANN) |
| **Status** | `INDEXING` → `COMPLETED` |

**Actions:**

```
5a. Build search document from extraction + analysis
    ├── Map fields via search_field_mappings (from doc-type config)
    │   ├── content = raw_text
    │   ├── summary = analysis.summary
    │   ├── risks = formatted risk items
    │   └── doc-type-specific fields
    └── Generate embedding vector
        └── text-embedding-3-small (1536 dimensions)

5b. Index to Cosmos DB
    ├── Container: search_index (partition key: /doc_type)
    ├── VectorSearchService.index_document()
    └── Stored with DiskANN vector index for similarity search
```

### Step 6: Completion

```
Pipeline completes → DocumentRecord.status = COMPLETED
                   → DocumentRecord.completed_at = now()
                   → DocumentRecord.extraction = ExtractionResult
                   → DocumentRecord.analysis = AnalysisResult
                   → All data persisted in Cosmos DB documents container
```

**Typical processing time:** 30–120 seconds depending on document size.

---

## 5. Agent Details & Tools

### 5.1 Ingestion Agent

```
src/documind/agents/ingestion/
├── agent.py              ← IngestionExecutor class
└── tools/
    └── tools.py          ← classify_doc_type, upload_document, store_to_blob
```

| Tool | Purpose | Azure Service |
|------|---------|---------------|
| `classify_doc_type()` | Match file to registered document type config | — (local registry) |
| `upload_document()` | Create DocumentRecord in Cosmos DB | Cosmos DB |
| `store_to_blob()` | Upload raw file to blob storage | Azure Blob Storage |

### 5.2 Extraction Agent

```
src/documind/agents/extraction/
├── agent.py              ← ExtractionExecutor class
└── tools/
    └── tools.py          ← extract_layout, extract_key_value_pairs, extract_tables
```

| Tool | Purpose | Azure Service |
|------|---------|---------------|
| `extract_layout()` | Run Document Intelligence OCR/layout model | Azure Document Intelligence |
| `extract_key_value_pairs()` | Parse form fields from DI result | — (local parsing) |
| `extract_tables()` | Convert grid data to structured tables | — (local parsing) |
| `build_extraction_result()` | Assemble composite ExtractionResult | — |

### 5.3 Analysis Agent

```
src/documind/agents/analysis/
├── agent.py              ← AnalysisExecutor class
├── prompts/              ← Jinja2 prompt templates
│   ├── rfp_summarize.j2
│   ├── contract_extract_clauses.j2
│   └── ...
└── tools/
    └── tools.py          ← summarize_document, extract_clauses, check_compliance, identify_risks
```

| Tool | Purpose | Azure Service |
|------|---------|---------------|
| `summarize_document()` | Generate executive summary | Azure OpenAI (GPT-4o) |
| `extract_clauses()` | Extract key contract clauses | Azure OpenAI (GPT-4o) |
| `check_compliance()` | Validate regulatory compliance | Azure OpenAI (GPT-4o) |
| `identify_risks()` | Identify risks with severity levels | Azure OpenAI (GPT-4o) |
| `build_analysis_result()` | Merge per-task outputs | — |

### 5.4 Search & Indexing Agent

```
src/documind/agents/search/
├── agent.py              ← SearchExecutor class
└── tools/
    └── tools.py          ← index_document, semantic_search, faceted_search
```

| Tool | Purpose | Azure Service |
|------|---------|---------------|
| `index_document()` | Generate embeddings and store in vector index | Azure OpenAI (Embeddings) + Cosmos DB |
| `semantic_search()` | Natural language search with cosine similarity | Cosmos DB DiskANN |
| `faceted_search()` | Aggregated search with facet counts | Cosmos DB |

### 5.5 Orchestrator

```
src/documind/agents/orchestrator/
├── workflow.py            ← DocumentPipeline (synchronous sequential workflow)
└── agent_workflow.py      ← Agent Framework wrapper (IngestionNode, ExtractionNode, etc.)
```

The orchestrator has two execution modes:

| Mode | Class | Use Case |
|------|-------|----------|
| **Synchronous** | `DocumentPipeline` | Direct execution, local dev |
| **Agent Framework** | `WorkflowBuilder` chain | Foundry deployment, production |

The Agent Framework wrapper uses `Executor` subclasses (`IngestionNode`, `ExtractionNode`, `AnalysisNode`, `SearchNode`) that pass `PipelineState` dict between nodes.

---

## 6. Azure Services & Resource Map

### 6.1 Service Dependency Matrix

| Azure Service | Purpose in DocuMind | Used By | SKU |
|---------------|---------------------|---------|-----|
| **Azure Blob Storage** | Store raw uploaded documents | Ingestion Agent | Standard GRS |
| **Azure Document Intelligence** | OCR, layout extraction, table/KV parsing | Extraction Agent | S0 |
| **Azure OpenAI — GPT-4o** | LLM analysis (summarize, risks, clauses) | Analysis Agent | Standard (30 TPM) |
| **Azure OpenAI — text-embedding-3-small** | Generate 1536-dim embeddings for search | Search Agent | Standard (30 TPM) |
| **Azure Cosmos DB (SQL API)** | Document state, metadata, vector search index | All Agents, API | Serverless |
| **Azure Key Vault** | Secrets management (keys, connection strings) | All Services | Standard |
| **Application Insights** | Distributed tracing, logging, live metrics | API, Pipeline | Per-GB |
| **Log Analytics Workspace** | Centralized log aggregation | App Insights | Per-GB |
| **Azure Container Apps** | Production hosting of FastAPI application | API Layer | Consumption |

### 6.2 Cosmos DB Schema

```
Database: documind
│
├── Container: documents
│   ├── Partition Key: /documentType
│   ├── Purpose: Pipeline state, extraction results, analysis results
│   └── Document shape:
│       {
│         "id": "<document_id>",
│         "documentType": "rfp",           ← partition key
│         "doc_type": "rfp",
│         "source_filename": "proposal.pdf",
│         "status": "completed",
│         "uploaded_at": "2026-04-25T...",
│         "completed_at": "2026-04-25T...",
│         "blob_url": "https://...blob.core...",
│         "extraction": { ... ExtractionResult ... },
│         "analysis": { ... AnalysisResult ... },
│         "error_message": null
│       }
│
└── Container: search_index
    ├── Partition Key: /doc_type
    ├── Purpose: Vector search index (DiskANN)
    └── Document shape:
        {
          "id": "<document_id>",
          "doc_type": "rfp",               ← partition key
          "source_filename": "proposal.pdf",
          "content": "<raw text>",
          "summary": "<executive summary>",
          "risks": "Risk 1 (high); Risk 2 (medium)",
          "page_count": 10,
          "embedding": [0.012, -0.034, ...]  ← 1536-dim vector
        }
```

### 6.3 Blob Storage Layout

```
Storage Account: documinddevst
│
├── Container: raw-documents/
│   └── {document_id}/{filename}       ← original uploads
│
├── Container: processed/
│   └── {document_id}/results.json     ← processed outputs (future)
│
└── Container: metadata/
    └── {document_id}/metadata.json    ← supplementary data (future)
```

---

## 7. Data Models & State Machine

### 7.1 Document Lifecycle State Machine

```
                    ┌─────────┐
   Upload ────────▶ │ PENDING │
                    └────┬────┘
                         │ Ingestion complete
                         ▼
                   ┌───────────┐
                   │EXTRACTING │
                   └─────┬─────┘
                         │ Extraction complete
                         ▼
                   ┌───────────┐
                   │ ANALYZING │
                   └─────┬─────┘
                         │ Analysis complete
                         ▼
                   ┌───────────┐
                   │ INDEXING  │
                   └─────┬─────┘
                         │ Indexing complete
                         ▼
                   ┌───────────┐
                   │ COMPLETED │
                   └───────────┘

        (Any stage failure)
              │
              ▼
         ┌────────┐
         │ FAILED │  ← error_message populated
         └────────┘
```

### 7.2 Core Data Flow

```
IngestionInput ──▶ IngestionOutput ──▶ ExtractionOutput ──▶ AnalysisOutput ──▶ SearchOutput
     │                   │                    │                    │                │
  file_bytes          record              extraction           analysis        index_result
  filename            file_bytes          ingestion            extraction      document_id
  doc_type_hint                                                                     
```

### 7.3 Key Domain Models

```
DocumentRecord
├── document_id: str (UUID)
├── doc_type: str
├── source_filename: str
├── status: ProcessingStatus
├── uploaded_at: datetime
├── completed_at: datetime | None
├── extraction: ExtractionResult | None
├── analysis: AnalysisResult | None
├── blob_url: str
└── error_message: str | None

ExtractionResult
├── page_count: int
├── key_value_pairs: list[KeyValuePair]
├── tables: list[ExtractedTable]
├── raw_text: str
├── confidence_score: float
└── metadata: dict

AnalysisResult
├── summary: str
├── risks: list[RiskItem]
│   └── RiskItem(title, description, severity, recommendation)
├── analyzed_at: datetime
└── metadata: dict
```

**Doc-type-specific extensions:**
- `RfpExtractionResult` — adds `issuing_organization`, `rfp_title`, `submission_deadline`, `requirements`, `evaluation_criteria`
- `ContractExtractionResult` — adds `parties`, `effective_date`, `contract_value`, `key_clauses`, `obligations`
- `RfpAnalysisResult` — adds `mandatory_requirements`, `optional_requirements`, `compliance_gaps`
- `ContractAnalysisResult` — adds `high_risk_clauses`, `missing_clauses`, `negotiation_points`

---

## 8. API Layer

### 8.1 Endpoint Map

```
FastAPI Application (port 8000)
│
├── POST   /documents                    ← Upload document (multipart/form-data)
│   └── Returns: 202 Accepted { document_id, status: "pending" }
│
├── GET    /documents/{id}               ← Poll processing status
│   └── Query: ?doc_type=rfp
│   └── Returns: { status, stages_completed, timestamps }
│
├── GET    /documents/{id}/analysis      ← Get full extraction + analysis results
│   └── Query: ?doc_type=rfp
│   └── Returns: { extraction: {...}, analysis: {...} }
│
├── POST   /search                       ← Semantic search across all documents
│   └── Body: { query, doc_type?, top, offset }
│   └── Returns: { results: [{ id, content, score, doc_type }] }
│
├── WS     /documents/{id}/ws            ← WebSocket live pipeline updates
│   └── Sends: PipelineEvent on each status change
│
├── GET    /documents/{id}/events        ← SSE live pipeline updates
│   └── For environments that block WebSocket
│
├── GET    /health                       ← Liveness probe (always 200)
│   └── Returns: { status: "healthy" }
│
└── GET    /ready                        ← Readiness probe
    └── Returns: { status: "ready"|"degraded", checks: [...] }
    └── Checks: Cosmos DB, Blob Storage, Azure OpenAI connectivity
```

### 8.2 Real-Time Updates

DocuMind supports three patterns for tracking pipeline progress:

| Pattern | Endpoint | Use Case |
|---------|----------|----------|
| **Polling** | `GET /documents/{id}` | Simple integration, any HTTP client |
| **WebSocket** | `WS /documents/{id}/ws` | Real-time dashboard, low latency |
| **Server-Sent Events** | `GET /documents/{id}/events` | Corporate proxies blocking WS |

Event format:
```json
{
  "document_id": "76a8f0d7-...",
  "stage": "analyzing",
  "status": "in_progress",
  "timestamp": "2026-04-25T14:37:30Z",
  "detail": "Running summarize task"
}
```

### 8.3 Authentication

Configured via `AUTH_MODE` environment variable:
- `none` — No auth (development)
- `api_key` — API key validation (staging)
- `entra_id` — Microsoft Entra ID / OAuth 2.0 (production)

---

## 9. Pluggable Document Types

DocuMind supports adding new document types by **dropping a YAML file** into `src/documind/doctypes/types/`. No code changes required.

### 9.1 Registered Document Types

| Type | Config File | DI Model | Analysis Tasks |
|------|-------------|----------|----------------|
| **RFP** | `rfp.yaml` | `prebuilt-layout` | summarize, extract_clauses, compliance_check |
| **Contract** | `contract.yaml` | `prebuilt-contract` | summarize, extract_clauses, compliance_check |
| **Spec** | `spec.yaml` | `prebuilt-layout` | summarize |

### 9.2 Document Type Configuration Schema

```yaml
name: rfp                              # Unique identifier
display_name: "Request for Proposal"
description: "RFP documents..."
version: "1.0"

supported_formats: [pdf, docx]         # Accepted file types
doc_intelligence_model: prebuilt-layout # Azure DI model to use

extraction_fields:                     # Fields to extract from document
  - name: issuing_organization
    label: "Issuing Organization"
    field_type: text                   # text, date, currency, list, table, boolean
    required: true
    description: "LLM hint for extraction"

analysis_tasks:                        # LLM tasks to run on extracted text
  - name: summarize
    prompt_template: rfp_summarize.j2  # Jinja2 template
    description: "Generate executive summary"

search_field_mappings:                 # How to index results for search
  - source_field: raw_text
    index_field: content
    searchable: true
    filterable: false
    facetable: false
```

### 9.3 Adding a New Document Type

1. Create `src/documind/doctypes/types/{name}.yaml`
2. Add prompt templates to `src/documind/agents/analysis/prompts/`
3. (Optional) Add specialized models to `src/documind/core/models/`
4. The `DocTypeRegistry` auto-discovers the new YAML on startup

---

## 10. Observability & Telemetry

### 10.1 Stack

```
Application Code
    │ OpenTelemetry SDK
    ▼
Azure Monitor Exporter
    │
    ▼
Application Insights ◄──── Log Analytics Workspace
    │
    ├── Distributed Traces (request → agent → service spans)
    ├── Application Logs (structured logging)
    ├── Live Metrics Stream (real-time)
    ├── Performance Metrics (latency, throughput)
    └── Failure Tracking (exceptions, errors)
```

### 10.2 Instrumented Components

| Component | Instrumentation |
|-----------|----------------|
| FastAPI | Auto-instrumented (request spans, route metrics) |
| Pipeline stages | Custom spans per agent (ingestion, extraction, analysis, indexing) |
| Azure SDK calls | Auto-instrumented via OTEL Azure SDK hooks |
| Cosmos DB | Request/response metrics, query duration |
| Blob Storage | Upload/download metrics |

### 10.3 Configuration

```python
# src/documind/core/tracing.py
configure_azure_monitor(
    connection_string=APPLICATIONINSIGHTS_CONNECTION_STRING,
    logger_name="documind",
    enable_live_metrics=True,
)
```

---

## 11. Azure Deployment Architecture

### 11.1 Development Architecture (Current)

```
                    ┌──────────────────────┐
                    │   Developer Machine  │
                    │   uvicorn :8000      │
                    │   .env credentials   │
                    └──────────┬───────────┘
                               │ Public endpoints
                               ▼
    ┌──────────────────────────────────────────────────────┐
    │              Azure (rg-documind-dev, eastus2)         │
    │                                                      │
    │  ┌──────────────┐    ┌──────────────────────┐        │
    │  │  Blob Storage │    │   Azure OpenAI       │        │
    │  │  documinddevst│    │   documind-dev-aoai  │        │
    │  │              │    │   ├── gpt-4o          │        │
    │  │  raw-documents│    │   └── text-embed-3-sm│        │
    │  │  processed   │    └──────────────────────┘        │
    │  │  metadata    │                                    │
    │  └──────────────┘    ┌──────────────────────┐        │
    │                      │  Document Intelligence│        │
    │  ┌──────────────┐    │  documind-dev-di     │        │
    │  │  Cosmos DB   │    └──────────────────────┘        │
    │  │  documind-dev│                                    │
    │  │  -cosmos     │    ┌──────────────────────┐        │
    │  │              │    │  Key Vault           │        │
    │  │  documents   │    │  documind-dev-kv     │        │
    │  │  search_index│    └──────────────────────┘        │
    │  └──────────────┘                                    │
    │                      ┌──────────────────────┐        │
    │                      │  App Insights        │        │
    │                      │  documind-dev-appi   │        │
    │                      │  + Log Analytics     │        │
    │                      └──────────────────────┘        │
    └──────────────────────────────────────────────────────┘
```

### 11.2 Production Architecture (Planned)

```
                        ┌────────────────────┐
                        │    Azure Front Door │
                        │    (Global CDN/WAF) │
                        └─────────┬──────────┘
                                  │ HTTPS (TLS 1.2+)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                 Azure (rg-documind-prod, eastus2)                        │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    Virtual Network (10.0.0.0/16)                   │  │
│  │                                                                   │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │  Subnet: snet-container-apps (10.0.1.0/24)                 │  │  │
│  │  │  NSG: Allow 443 inbound from Front Door only               │  │  │
│  │  │                                                             │  │  │
│  │  │  ┌────────────────────────────────────────────────────┐    │  │  │
│  │  │  │  Container App Environment                        │    │  │  │
│  │  │  │  ┌──────────────────────┐                         │    │  │  │
│  │  │  │  │  documind-api        │                         │    │  │  │
│  │  │  │  │  FastAPI container   │                         │    │  │  │
│  │  │  │  │  1-10 replicas       │                         │    │  │  │
│  │  │  │  │  CPU: 1, Mem: 2Gi   │                         │    │  │  │
│  │  │  │  │  Managed Identity   │                         │    │  │  │
│  │  │  │  └──────────┬───────────┘                         │    │  │  │
│  │  │  │             │ Managed Identity (no secrets)       │    │  │  │
│  │  │  └─────────────┼────────────────────────────────────┘    │  │  │
│  │  └────────────────┼────────────────────────────────────────┘  │  │
│  │                   │                                            │  │
│  │  ┌────────────────▼────────────────────────────────────────┐  │  │
│  │  │  Subnet: snet-private-endpoints (10.0.2.0/24)          │  │  │
│  │  │  NSG: Allow inbound only from snet-container-apps      │  │  │
│  │  │                                                         │  │  │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │  │  │
│  │  │  │PE: Cosmos DB│  │PE: Blob     │  │PE: Key Vault│    │  │  │
│  │  │  │10.0.2.4     │  │Storage      │  │10.0.2.6     │    │  │  │
│  │  │  │             │  │10.0.2.5     │  │             │    │  │  │
│  │  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │  │  │
│  │  │         │                │                │            │  │  │
│  │  │  ┌──────┴──────┐  ┌─────┴──────┐  ┌─────┴──────┐    │  │  │
│  │  │  │PE: Azure    │  │PE: Doc     │  │PE: App     │    │  │  │
│  │  │  │OpenAI       │  │Intelligence│  │Insights    │    │  │  │
│  │  │  │10.0.2.7     │  │10.0.2.8    │  │10.0.2.9    │    │  │  │
│  │  │  └─────────────┘  └────────────┘  └────────────┘    │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │                                                            │  │
│  │  Private DNS Zones (linked to VNet):                       │  │
│  │  ├── privatelink.documents.azure.com (Cosmos DB)           │  │
│  │  ├── privatelink.blob.core.windows.net (Blob Storage)      │  │
│  │  ├── privatelink.vaultcore.azure.net (Key Vault)           │  │
│  │  ├── privatelink.openai.azure.com (Azure OpenAI)           │  │
│  │  ├── privatelink.cognitiveservices.azure.com (Doc Intel)   │  │
│  │  └── privatelink.monitor.azure.com (App Insights)          │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  PaaS Services (Public access DISABLED)                    │  │
│  │                                                            │  │
│  │  ┌─────────────┐  ┌──────────────────┐  ┌──────────┐     │  │
│  │  │ Cosmos DB   │  │ Azure OpenAI     │  │ Blob     │     │  │
│  │  │ Serverless  │  │ GPT-4o           │  │ Storage  │     │  │
│  │  │ Session     │  │ text-embed-3-sm  │  │ GRS      │     │  │
│  │  │ consistency │  │ 100 TPM (prod)   │  │          │     │  │
│  │  └─────────────┘  └──────────────────┘  └──────────┘     │  │
│  │                                                            │  │
│  │  ┌─────────────┐  ┌──────────────────┐  ┌──────────┐     │  │
│  │  │ Doc Intel   │  │ Key Vault        │  │ App      │     │  │
│  │  │ S0          │  │ RBAC-enabled     │  │ Insights │     │  │
│  │  │             │  │ Purge protection │  │ + LAW    │     │  │
│  │  └─────────────┘  └──────────────────┘  └──────────┘     │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Identity & Access (RBAC — no keys/secrets at runtime)    │  │
│  │                                                            │  │
│  │  Container App Managed Identity ──▶ Role Assignments:     │  │
│  │  ├── Cognitive Services User        → Azure OpenAI        │  │
│  │  ├── Cognitive Services User        → Doc Intelligence    │  │
│  │  ├── Storage Blob Data Contributor  → Blob Storage        │  │
│  │  ├── Cosmos DB Built-in Data Contr. → Cosmos DB           │  │
│  │  └── Key Vault Secrets User         → Key Vault           │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 12. Production Networking & Security

### 12.1 Network Topology

| Component | Subnet | CIDR | Purpose |
|-----------|--------|------|---------|
| Container Apps Environment | `snet-container-apps` | `10.0.1.0/24` | Application hosting |
| Private Endpoints | `snet-private-endpoints` | `10.0.2.0/24` | PaaS service access |

### 12.2 Network Security Groups (NSGs)

**snet-container-apps NSG:**

| Rule | Priority | Direction | Source | Destination | Port | Action |
|------|----------|-----------|--------|-------------|------|--------|
| Allow-FrontDoor-Inbound | 100 | Inbound | AzureFrontDoor.Backend | * | 443 | Allow |
| Allow-HealthProbe | 110 | Inbound | AzureLoadBalancer | * | * | Allow |
| Deny-All-Inbound | 4096 | Inbound | * | * | * | Deny |
| Allow-PrivateEndpoints | 100 | Outbound | * | snet-private-endpoints | 443 | Allow |
| Allow-AzureMonitor | 200 | Outbound | * | AzureMonitor | 443 | Allow |
| Deny-Internet-Outbound | 4096 | Outbound | * | Internet | * | Deny |

**snet-private-endpoints NSG:**

| Rule | Priority | Direction | Source | Destination | Port | Action |
|------|----------|-----------|--------|-------------|------|--------|
| Allow-ContainerApps | 100 | Inbound | snet-container-apps | * | 443 | Allow |
| Deny-All-Inbound | 4096 | Inbound | * | * | * | Deny |

### 12.3 Private Endpoints

| Service | Private DNS Zone | Purpose |
|---------|-----------------|---------|
| Cosmos DB | `privatelink.documents.azure.com` | Database access |
| Blob Storage | `privatelink.blob.core.windows.net` | Document storage |
| Azure OpenAI | `privatelink.openai.azure.com` | LLM inference |
| Document Intelligence | `privatelink.cognitiveservices.azure.com` | OCR/extraction |
| Key Vault | `privatelink.vaultcore.azure.net` | Secrets access |
| App Insights | `privatelink.monitor.azure.com` | Telemetry ingestion |

### 12.4 Security Controls Summary

| Control | Dev | Prod |
|---------|-----|------|
| **Authentication** | None / API Key | Microsoft Entra ID (OAuth 2.0) |
| **Network Access** | Public endpoints | Private endpoints only |
| **Secrets Management** | `.env` file | Key Vault + Managed Identity |
| **Identity** | Connection strings | Managed Identity (zero secrets) |
| **TLS** | 1.2+ (Azure default) | 1.2+ enforced |
| **WAF** | None | Azure Front Door WAF policies |
| **Data Encryption** | At rest (Azure default) | At rest + in transit + CMK option |
| **CORS** | Allow all (*) | Restrict to frontend domain |
| **Audit Logging** | App Insights | App Insights + Azure Activity Log |

---

## 13. Infrastructure as Code

### 13.1 Terraform Module Dependency Graph

```
infra/main.tf (root)
│
├── module "resource_group"
│   └── azurerm_resource_group
│
├── module "monitoring"                  ← depends_on: resource_group
│   ├── azurerm_log_analytics_workspace
│   └── azurerm_application_insights
│
├── module "storage"                     ← depends_on: resource_group
│   ├── azurerm_storage_account (GRS, TLS 1.2)
│   └── azurerm_storage_container × 3
│       ├── raw-documents
│       ├── processed
│       └── metadata
│
├── module "keyvault"                    ← depends_on: resource_group
│   └── azurerm_key_vault (RBAC-enabled)
│
├── module "ai_services"                 ← depends_on: resource_group
│   ├── azurerm_cognitive_account (kind=OpenAI)
│   └── azurerm_cognitive_deployment × 2
│       ├── gpt-4o (v2024-11-20)
│       └── text-embedding-3-small (v1)
│
├── module "document_intelligence"       ← depends_on: resource_group
│   └── azurerm_cognitive_account (kind=FormRecognizer)
│
├── module "cosmos_db"                   ← depends_on: resource_group
│   ├── azurerm_cosmosdb_account (Serverless, Session consistency)
│   ├── azurerm_cosmosdb_sql_database (documind)
│   └── azurerm_cosmosdb_sql_container × 2
│       ├── documents (/documentType)
│       └── search_index (/doc_type)
│
├── module "ai_search" (OPTIONAL)        ← gated by var.enable_ai_search
│   └── azurerm_search_service
│
├── module "container_apps" (OPTIONAL)   ← gated by var.enable_container_apps
│   ├── azurerm_container_app_environment
│   └── azurerm_container_app (1-10 replicas, managed identity)
│
└── module "identity" (OPTIONAL)
    └── azurerm_role_assignment × N (RBAC bindings)
```

### 13.2 Environment Configurations

| Variable | Dev | Prod |
|----------|-----|------|
| `environment` | `dev` | `prod` |
| `gpt_capacity` | 10 TPM | 100 TPM |
| `enable_container_apps` | `false` | `true` |
| `enable_ai_search` | `false` | `false` |
| `doc_intelligence_sku` | `S0` | `S0` |
| `location` | `eastus2` | `eastus2` |

### 13.3 Deployment Commands

```bash
# Deploy infrastructure
cd infra
terraform init
terraform plan -var-file="environments/dev.tfvars"
terraform apply -var-file="environments/dev.tfvars"

# Deploy application (via Azure Developer CLI)
azd up

# Or via Docker + Container Apps
docker build -t documind:latest .
az containerapp update --name documind-prod-api --image documind:latest
```

---

## 14. Scalability & Performance

### 14.1 Throughput Characteristics

| Stage | Latency (typical) | Bottleneck | Scaling Strategy |
|-------|-------------------|------------|------------------|
| Ingestion | 1–3s | Blob upload bandwidth | Parallel uploads |
| Extraction | 5–15s | Document Intelligence API | DI tier upgrade (S0 → S0 with higher QPM) |
| Analysis | 15–60s | GPT-4o token processing | Increase TPM capacity, parallel tasks |
| Indexing | 3–8s | Embedding generation | Batch embeddings |
| **Total** | **30–120s** | Analysis stage | — |

### 14.2 Scaling Levers

| Component | Scaling Mechanism | Dev | Prod |
|-----------|-------------------|-----|------|
| **API** | Container Apps replicas | 1 | 1–10 (auto-scale on CPU) |
| **GPT-4o** | TPM (Tokens Per Minute) | 10K | 100K+ |
| **Embeddings** | TPM | 10K | 100K+ |
| **Cosmos DB** | Serverless (auto-scale RU/s) | Serverless | Serverless or Provisioned |
| **Doc Intelligence** | QPM (Queries Per Minute) | S0 (15 QPM) | S0 (custom quota) |
| **Blob Storage** | Inherently scalable | Standard | Standard |

### 14.3 Future Enhancements

- **Parallel analysis tasks** — Run summarize, extract_clauses, and compliance_check concurrently
- **Batch document processing** — Queue-based processing with Azure Service Bus
- **Caching** — Redis cache for repeated searches and embeddings
- **Multi-region** — Cosmos DB multi-region writes for global deployment
- **Chunked streaming** — Stream analysis results as they complete via WebSocket

---

*DocuMind — EPAM Practice Accelerator · Azure AI Platform · Terraform + Python*
