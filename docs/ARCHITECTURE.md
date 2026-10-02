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
11. [Offline / Local Mode](#11-offline--local-mode)
12. [RAG Q&A (/ask)](#12-rag-qa-ask)
13. [Azure Deployment Architecture](#13-azure-deployment-architecture)
14. [Production Networking & Security](#14-production-networking--security)
15. [Infrastructure as Code](#15-infrastructure-as-code)
16. [Scalability & Performance](#16-scalability--performance)

---

## 1. Executive Summary

DocuMind is an **AI-powered document processing accelerator** that ingests enterprise documents (RFPs, contracts, technical specs), extracts structured data, runs LLM-based analysis, indexes results for semantic search, and answers grounded questions via a **RAG `/ask` endpoint** — all orchestrated through a **multi-agent pipeline** built on Microsoft Agent Framework.

The same codebase runs in three modes selected by env vars (`BACKEND`, `LOCAL_LLM_PROVIDER`):

- **Azure** — Azure OpenAI (GPT-4o) + Document Intelligence + Cosmos DB (vector) + Blob Storage + managed identity. Production path.
- **Offline + Gemini** — Google Gemini (cloud LLM) + ChromaDB + SQLite + local filesystem + `sentence-transformers` embeddings + local file extractors. Fast local dev.
- **Offline + Ollama** — Ollama (local LLM) + same offline vector/metadata/blob stack. Fully air-gapped.

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
│  │  SERVICES FACTORY  (src/documind/services/factory.py)           │  │
│  │  Chooses Azure vs local impls by env (BACKEND, LOCAL_LLM_PROVIDER)│  │
│  │  get_llm_caller · get_llm_text_caller · get_embedding_fn        │  │
│  │  get_search_service · get_document_store · get_blob_store       │  │
│  │  get_extraction_service · PromptLoader · DocumentChunker        │  │
│  └──┬─────────┬─────────────┬─────────────┬───────────────────────┘   │
│     │         │             │             │                            │
│  ┌──▼─────────▼─────────────▼─────────────▼────────────────────────┐  │
│  │  PLATFORM — picked at runtime                                   │  │
│  │  Azure mode : OpenAI · Doc Intelligence · Cosmos DB · Blob      │  │
│  │  Offline    : Gemini OR Ollama · ChromaDB · SQLite · filesystem │  │
│  │  Shared     : Key Vault · App Insights · Log Analytics (Azure)  │  │
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

### 6.4 Offline / Local Service Equivalents

When `BACKEND=local`, the Services Factory wires every Azure dependency to a drop-in local replacement. Agent code is unchanged.

| Concern | Azure mode | Offline mode | Factory accessor |
|---------|------------|--------------|------------------|
| **LLM (JSON extraction)** | Azure OpenAI (GPT-4o) | Gemini (`gemini-3.5-flash`) **or** Ollama (`llama3.x`) | `get_llm_caller()` |
| **LLM (free-text / RAG)** | Azure OpenAI (GPT-4o) | Gemini **or** Ollama (same provider, `force_json=False`) | `get_llm_text_caller()` |
| **Embeddings** | `text-embedding-3-small` (1536-d) | `sentence-transformers/all-MiniLM-L6-v2` (384-d, CPU) | `get_embedding_fn()` |
| **Vector search** | Cosmos DB (DiskANN) | ChromaDB persistent client (`./data/chroma/`) | `get_search_service()` |
| **Document store** | Cosmos DB (`documents` container) | SQLite (`./data/documind.sqlite`) | `get_document_store()` |
| **Blob storage** | Azure Blob Storage | Local filesystem (`./data/blobs/`) | `get_blob_store()` |
| **Extraction** | Azure Document Intelligence | PyMuPDF + python-docx + openpyxl | `get_extraction_service()` |
| **Auth** | Entra ID / API key | `AUTH_MODE=none` | middleware |

Source:

```
src/documind/services/
├── factory.py                 # Mode selector (BACKEND / LOCAL_LLM_PROVIDER)
├── cosmos.py                  # Azure document store
├── blob_storage.py            # Azure blob store
├── vector_search.py           # Azure (Cosmos) vector search
└── local/
    ├── chroma_search.py       # ChromaDB vector search
    ├── sqlite_store.py        # SQLite document store
    ├── filesystem_blob.py     # Local filesystem blob store
    ├── gemini_llm.py          # Google Gemini client (with retry/backoff)
    ├── ollama_llm.py          # Ollama HTTP client
    └── local_extractor.py     # PyMuPDF / python-docx / openpyxl
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
├── GET    /documents/{id}               ← Poll processing status + stage history
│   └── Query: ?doc_type=rfp (optional; omit for auto-detect)
│   └── Returns: { status, stages_completed, timestamps, error_message? }
│
├── GET    /documents/{id}/analysis      ← Full extraction + analysis results
│   └── Query: ?doc_type=rfp (optional)
│   └── Returns: { extraction: {...}, analysis: {...} }
│
├── POST   /search                       ← Semantic search across indexed corpus
│   └── Body: { query, doc_type?, top, offset }
│   └── Returns: { results: [{ id, content, score, doc_type }] }
│
├── POST   /ask                          ← RAG Q&A (retrieve + ground + answer)
│   └── Body: { question, doc_type?, top }
│   └── Returns: { question, answer, citations: [{ id, score, preview, doc_type }] }
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
├── GET    /ready                        ← Readiness probe
│   └── Returns: { status: "ready"|"degraded", checks: [...] }
│   └── Checks: metadata store, vector store, LLM provider connectivity
│
└── *      /mcp                          ← MCP server (Streamable HTTP mount)
    └── Tools: list_doc_types, summarize, extract_clauses, check_compliance
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

## 11. Offline / Local Mode

DocuMind can run end-to-end with **no Azure resources** by setting `BACKEND=local`. The factory in [`src/documind/services/factory.py`](../src/documind/services/factory.py) swaps every Azure wrapper for a local implementation at startup.

### 11.1 Mode Selection

```
       ┌────────────────────────────────────────┐
       │  Settings (pydantic-settings, .env)       │
       │  BACKEND            = azure | local      │
       │  LOCAL_LLM_PROVIDER = gemini | ollama    │
       │  AUTH_MODE          = entra_id|api_key|none│
       └──────────────────┬────────────────────┘
                          ▼
       ┌────────────────────────────────────────┐
       │           services.factory               │
       │  get_llm_caller()                        │
       │  get_llm_text_caller()        (RAG)      │
       │  get_embedding_fn()                      │
       │  get_search_service()                    │
       │  get_document_store()                    │
       │  get_blob_store()                        │
       │  get_extraction_service()                │
       └───────────┬───────────────────────────┘
              ┌────────┴──────────┐
              ▼                   ▼
       Azure wrappers       Local wrappers
       (cosmos, blob,       (sqlite_store,
        openai, docint,      filesystem_blob,
        vector_search)       chroma_search,
                             gemini_llm,
                             ollama_llm,
                             local_extractor)
```

Factory accessors are `@functools.lru_cache(maxsize=1)` singletons — one instance per process. `get_llm_caller()` returns a **JSON-mode** caller used by the Analysis agent; `get_llm_text_caller()` returns a **free-text** caller used by `/ask`.

### 11.2 Offline Pipeline Flow

The four pipeline stages run **unchanged** against the local backends:

```
Upload                                                             │
  │                                                                │
  ▼                                                                │
Ingestion    ───  filesystem_blob.put_object()  ───▶  ./data/blobs/│
  │          ───  sqlite_store.upsert(record=PENDING)              │
  ▼                                                                │
Extraction   ───  local_extractor.extract(file_bytes, mime)         │
  │               (PyMuPDF / python-docx / openpyxl)                │
  ▼                                                                │
Analysis     ───  get_llm_caller() in JSON mode                     │
  │               (Gemini: response_mime_type=application/json      │
  │                Ollama: format=json)                             │
  ▼                                                                │
Indexing     ───  sentence-transformers embeddings (384-d, CPU)     │
  │          ───  chroma_search.upsert(id, text, embedding, meta) │
  │          ───  sqlite_store.upsert(record=COMPLETED,            │
  │                                 stages_completed=[…])          │
  ▼                                                                │
REST / UI / MCP / /ask share the same Chroma collection + SQLite  │
```

### 11.3 LLM Providers (offline)

| Provider | Transport | JSON mode | RAG mode | Env | Notes |
|----------|-----------|-----------|----------|-----|-------|
| **Gemini** | `google-genai` SDK | `response_mime_type=application/json` | plain text | `GEMINI_API_KEY`, `GEMINI_MODEL` | Cloud; retries 429/503 with exponential backoff; recommended for interactive dev |
| **Ollama** | HTTP (`/api/generate`) | `format=json` | plain text | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Fully air-gapped; CPU inference is slow (minutes) |

Switching providers is a single env change — `LOCAL_LLM_PROVIDER=gemini` or `=ollama` — and a process restart. The Analysis agent is provider-agnostic.

### 11.4 Offline Readiness Probe

`GET /ready` adapts its checks per mode:

```json
{
  "status": "ready",
  "checks": [
    { "name": "sqlite",    "status": "ok" },
    { "name": "chromadb",  "status": "ok" },
    { "name": "gemini",    "status": "ok", "detail": "model=gemini-3.5-flash" }
  ]
}
```

### 11.5 On-Disk Layout

```
./data/
├── chroma/            # ChromaDB persistent store (HNSW cosine)
├── documind.sqlite    # SQLite DocumentRecord table
└── blobs/
    └── documents/<document_id>/<filename>
```

Delete `./data/` to reset the offline install.

### 11.6 Limitations

- **No OCR** — image-only PDFs yield empty content (offline extractor has no fallback to Azure Document Intelligence).
- **Smaller embeddings** — 384-d vs 1536-d. Semantic quality is lower; keep `top` higher for RAG recall.
- **Single-writer SQLite** — avoid parallel pipelines against the same `./data/documind.sqlite`.
- **No RBAC** — offline mode intentionally runs with `AUTH_MODE=none`; do not expose to the public internet.

See [RUNNING-OFFLINE.md](../RUNNING-OFFLINE.md) for the operator runbook.

---

## 12. RAG Q&A (/ask)

`POST /ask` is a thin retrieval-augmented generation layer that reuses the same vector store the pipeline writes to.

### 12.1 Request / Response

```http
POST /ask
Content-Type: application/json

{ "question": "Who are the parties in the agreement?",
  "doc_type": "contract",
  "top": 5 }
```

```json
{
  "question": "Who are the parties in the agreement?",
  "answer":   "The parties are Alpine Solutions Group, LLC ... and Woodgrove Bank, N.A. [1].",
  "citations": [
    { "id": "1e4b3eb1-…", "doc_type": "contract",
      "score": 0.57, "preview": "PROFESSIONAL SERVICES AGREEMENT …" }
  ]
}
```

### 12.2 Pipeline

```
/ask body
   │
   ▼
factory.get_search_service()
   │  semantic_search(query, top, filter=doc_type?)       ← Chroma or Cosmos DB
   │  returns [{id, content, score, doc_type, …}]
   ▼
Build grounded prompt
   │  [n] (id=…, type=…) <content truncated to 1800 chars>
   │  Rules: cite [n]; refuse if sources insufficient
   ▼
factory.get_llm_text_caller()                           ← free-text LLM (no JSON mode)
   │  returns answer string
   ▼
Assemble AskResponse
   │  answer + citations (first 240 chars of each hit)
   ▼
200 OK
```

### 12.3 Grounding Rules

The prompt (see [`src/documind/api/endpoints/ask.py`](../src/documind/api/endpoints/ask.py)) enforces three guarantees:

1. **Source-only answers** — the model is told to use ONLY the context passages.
2. **Explicit refusal** — if sources are insufficient, it must reply exactly: *“The provided documents do not contain enough information to answer.”*
3. **Inline citations** — each supporting statement cites `[n]` matching a numbered source block.

### 12.4 Backend Compatibility

| Mode | Retrieval | Generation |
|------|-----------|------------|
| Azure | Cosmos DB vector search | Azure OpenAI (GPT-4o) |
| Offline + Gemini | ChromaDB | Gemini (text) |
| Offline + Ollama | ChromaDB | Ollama (text) |

The endpoint code is identical across modes — only the factory wiring differs.

---

## 13. Azure Deployment Architecture

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

## 14. Production Networking & Security

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

## 15. Infrastructure as Code

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

## 16. Scalability & Performance

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
