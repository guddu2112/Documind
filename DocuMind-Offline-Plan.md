# DocuMind — Offline / ChromaDB Migration Plan

> Goal: Run the entire DocuMind pipeline on a developer laptop with **no Azure
> dependencies**. Vector search is powered by ChromaDB; the LLM runs via Ollama;
> embeddings via sentence-transformers; blobs on the local filesystem; metadata
> in SQLite. The existing Azure code path is kept and selected via
> `BACKEND=azure|local` so the same repo runs both ways.

---

## 1. Confirmed choices

| Concern | Azure (current) | Offline (target) |
|---|---|---|
| LLM (analysis) | Azure OpenAI GPT-4o | **Ollama** (`llama3.1:8b`) |
| Embeddings | text-embedding-3-small (1536-d) | **sentence-transformers** `all-MiniLM-L6-v2` (384-d) |
| Vector search | Cosmos DB DiskANN | **ChromaDB** (persistent, local) |
| Metadata / pipeline state | Cosmos DB (documents container) | **SQLite** (single file) |
| File storage | Azure Blob Storage | **Local filesystem** (`./data/blobs/`) |
| OCR / Layout | Azure Document Intelligence | **PyMuPDF + python-docx + openpyxl** (no OCR) |
| Secrets | Key Vault | `.env.local` only |
| Telemetry | App Insights (OTEL) | Console logging only (exporter disabled) |
| Auth | Optional API key | Off by default for local |
| Hosting | ACR → Container Apps | `uvicorn` + Vite dev server |

**Backend switch:** `BACKEND=local` (default) or `BACKEND=azure`.
Selected via `documind.core.config.settings.Settings.backend`.

---

## 2. Architecture — how the swap works

The current code is already dependency-injected through `_build_pipeline()` in
[src/documind/api/endpoints/documents.py](src/documind/api/endpoints/documents.py)
and the FastAPI DI providers in
[src/documind/api/dependencies.py](src/documind/api/dependencies.py).

We keep the interfaces, add local implementations behind a factory, and select
via `settings.backend`.

```
                       ┌───────────────────────────────────┐
                       │      _build_pipeline() /          │
                       │   dependencies.py factories       │
                       └───────────────────────────────────┘
                                     │
                        settings.backend == "local"?
                                     │
                ┌────────────────────┴───────────────────┐
                │                                        │
            LOCAL BACKENDS                          AZURE BACKENDS
   SQLiteStore    ↔ CosmosService              CosmosService
   ChromaSearch   ↔ VectorSearchService        VectorSearchService
   FSBlobStore    ↔ BlobStorageService         BlobStorageService
   LocalExtractor ↔ DocumentIntelligence...    DocumentIntelligenceService
   OllamaCaller   ↔ Azure OpenAI llm_caller    Azure OpenAI llm_caller
   STEmbedder     ↔ Azure OpenAI embedding_fn  Azure OpenAI embedding_fn
```

None of the agents (`IngestionExecutor`, `ExtractionExecutor`,
`AnalysisExecutor`, `SearchExecutor`), orchestrator, doc-type registry,
prompts, chunker, or API endpoints change.

---

## 3. Public interfaces we must preserve

To avoid touching agents, the local classes replicate exactly these methods:

**`CosmosService`** — `create_record`, `get_record`, `upsert_record`,
`update_status`, `query_by_status`.
- Add one new method used by the WebSocket/SSE endpoint:
  `query_by_document_id(document_id)` — returns the record (or None) without
  needing a partition key. Trivial in SQLite; wraps existing cross-partition
  query in the Cosmos version.

**`VectorSearchService`** — `index_document(dict)`, `semantic_search(query, top, filters)`,
`faceted_search(query, facets, top)`.
- `filters` currently accepts a Cosmos SQL fragment like `"c.doc_type = 'rfp'"`.
  The local implementation will parse the common `c.doc_type = '<value>'` pattern
  and translate it to a Chroma `where` filter. Anything unrecognised is ignored.

**`BlobStorageService`** — `upload_document(bytes, filename, container, document_id, content_type)`
returns a URL/path string; `download_document(container, blob_path)`; `list_blobs`.

**`DocumentIntelligenceService`** — `analyze_document(file_bytes, model_id)`,
`extract_text(result)`, `extract_key_value_pairs(result)`,
`extract_tables(result)`, `get_page_count(result)`.
- The local `analysis_result` will be a small dataclass exposing the same
  attributes (`content`, `pages`, `key_value_pairs`, `tables`) so the current
  parsers work unchanged. `model_id` is accepted for API compatibility but
  ignored (all local extraction uses layout heuristics).
- Supported formats added: **PDF** (PyMuPDF), **DOCX** (python-docx),
  **XLSX** (openpyxl), **TXT / MD** (plain read — needed so
  `samples/**/*.txt` can flow through the smoke test).
- PNG/JPG/TIFF without OCR return empty text + a warning. Doc-type YAML
  configs that list these formats still accept the upload but produce empty
  extraction; documented in `RUNNING-OFFLINE.md`.

**LLM caller** — `Callable[[str], str]`. Ollama caller wraps `/api/chat`
with a low temperature to produce clean JSON.

**Embedding fn** — `Callable[[str], list[float]]`. Uses sentence-transformers
with lazy model load.

---

## 4. File-by-file changes

### New files
- `src/documind/services/local/__init__.py`
- `src/documind/services/local/sqlite_store.py` — SQLite-backed
  `LocalRecordStore` (mirrors `CosmosService`).
- `src/documind/services/local/chroma_search.py` — `ChromaSearchService`.
- `src/documind/services/local/filesystem_blob.py` — `LocalBlobStorage`.
- `src/documind/services/local/local_extractor.py` — `LocalExtractor` +
  `LocalAnalysisResult` dataclass.
- `src/documind/services/local/ollama_llm.py` — `make_ollama_caller()` and
  `make_st_embedder()`.
- `src/documind/services/factory.py` — `get_record_store()`,
  `get_search_service()`, `get_blob_store()`, `get_extractor()`,
  `get_llm_caller()`, `get_embedding_fn()`. Reads `settings.backend`.
- `.env.local.template` — offline env vars.
- `RUNNING-OFFLINE.md` — quick-start guide.
- `tests/offline/test_local_pipeline.py` — end-to-end smoke test using a file
  from `samples/`.

### Modified files
- `src/documind/core/config/settings.py` — add:
  ```
  backend: Literal["azure","local"] = "local"
  chroma_path: str = "./data/chroma"
  chroma_collection: str = "documind"
  sqlite_path: str = "./data/documind.sqlite"
  local_blob_dir: str = "./data/blobs"
  ollama_base_url: str = "http://localhost:11434"
  ollama_model: str = "llama3.1:8b"
  ollama_timeout_seconds: int = 300
  local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
  local_embedding_dim: int = 384
  auth_mode: str = "none"  # override current api_key default so /documents works locally
  ```
  Also make Azure fields tolerate empty values when `backend == "local"`.
- `src/documind/api/dependencies.py` — route the four singletons through the
  factory when `backend == "local"`.
- `src/documind/api/endpoints/documents.py` — replace the inline
  `llm_caller`/`VectorSearchService()`/etc. with factory calls (both in
  `_build_pipeline` and in the `_run_pipeline_background` fallback that
  currently instantiates `CosmosService()` directly to mark FAILED).
- `src/documind/api/endpoints/search.py` — factory for search service.
- `src/documind/api/endpoints/health.py` — `/ready` currently calls
  Cosmos/Blob/AzureOpenAI unconditionally; add local checks
  (SQLite reachable, ChromaDB collection exists, Ollama `/api/tags` returns 200).
- `src/documind/api/endpoints/events.py` — replaces direct `CosmosService()` +
  `cosmos._container.query_items(...)` with the factory's record store,
  polling by `document_id` cross-partition. Needs a new
  `query_by_document_id(document_id)` on the store protocol; SQLite
  implementation is trivial, Cosmos implementation wraps the existing
  cross-partition query so behaviour is preserved.
- `src/documind/mcp/server.py` — replace hardcoded `_get_llm_caller()`
  (Azure OpenAI) with the factory's `get_llm_caller()`.
- `src/documind/core/tracing.py` — already a no-op when
  `APPLICATIONINSIGHTS_CONNECTION_STRING` is empty (verified — falls back to
  in-memory `TracerProvider`). **No change needed**, just document it.
- `pyproject.toml` — add `[project.optional-dependencies].offline`:
  ```
  offline = [
      "chromadb>=0.5.0",
      "sentence-transformers>=3.0.0",
      "ollama>=0.3.0",
      "pymupdf>=1.24.0",
      "python-docx>=1.1.0",
      "openpyxl>=3.1.0",
      "sqlalchemy>=2.0.0",
  ]
  ```
- `Makefile` — add:
  - `install-offline` → `pip install -e ".[offline]"`
  - `dev-offline` → runs API + web with `BACKEND=local`, sets env from
    `.env.local`.

### Untouched (verified)
- All agents in `src/documind/agents/**` (including `SearchExecutor` — see
  note below on `SearchService` type hint).
- `src/documind/doctypes/**` (registry, YAML configs, `search_field_mappings`
  which we just flatten into Chroma metadata).
- `src/documind/agents/analysis/prompts/**`.
- `src/documind/services/chunker.py`, `prompt_loader.py`.
- Terraform, `azure.yaml`, hooks — kept for the Azure path.
- `src/documind/agents/orchestrator/agent_workflow.py` — the Foundry-hosted
  workflow variant. It imports `agent_framework` and `FoundryChatClient` and
  is **not** used by the default `_build_pipeline` (which uses
  `DocumentPipeline` from `workflow.py`). We leave it in place; it just
  isn't reachable in local mode.
- `src/documind/services/cosmos_vector_setup.py` — provisioning-time helper,
  not called by the API. Left as-is for the Azure path.
- `Dockerfile` — kept as the Azure/production image. **Not** producing an
  offline Docker image (out of scope). Local run is bare-metal `uvicorn` +
  Vite.
- `web/vite.config.ts` — already proxies to `127.0.0.1:8000`; no change.
- `tests/` (existing) — all Azure paths are mocked in `tests/conftest.py`,
  so `make test` keeps passing. We only *add* `tests/offline/`.

### Compatibility notes
- **`SearchExecutor` type hint**: `agents/search/agent.py` and its
  `tools/tools.py` type-hint on `SearchService` (the old Azure AI Search
  wrapper). Runtime is duck-typed, so passing `ChromaSearchService` or
  `VectorSearchService` works today. **Optional** cleanup: widen those hints
  to `SearchProtocol` from `core/protocols.py`. Not required to make offline
  mode run.
- **`src/documind/services/__init__.py`** re-exports `SearchService`,
  `CosmosService`, `BlobStorageService`, etc. Importing the package pulls in
  the Azure SDKs. That's OK — the Azure SDKs stay in `[project.dependencies]`
  so `pip install -e .[offline]` still installs them; the offline path just
  never calls them.

---

## 5. Data layout on disk

```
./data/
├── documind.sqlite          # metadata + pipeline state
├── chroma/                  # ChromaDB persistence dir
│   └── ... (Chroma-managed files)
└── blobs/
    ├── raw-documents/
    │   └── <document_id>/<filename>
    └── processed/
        └── <document_id>/<filename>
```

All under a single `./data/` directory that `.gitignore` will exclude.

---

## 6. Bootstrap steps (what the user runs)

```powershell
# 1. Install Ollama and pull the model (one-time)
#    https://ollama.com/download
ollama pull llama3.1:8b

# 2. Python env + offline extras
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[offline]"

# 3. Environment
Copy-Item .env.local.template .env

# 4. Run everything
make dev-offline
```

First run downloads the sentence-transformer model (~90 MB, cached to
`~/.cache/huggingface`). Everything after that is fully offline.

---

## 7. Smoke test plan

`tests/offline/test_local_pipeline.py`:
1. Set `BACKEND=local`, temp `./data/` dir.
2. Feed `samples/contracts/software-license-agreement.txt` through
   `DocumentPipeline`.
3. Assert the record moves PENDING → COMPLETED.
4. Assert the SQLite row exists.
5. Assert `ChromaSearchService.semantic_search("license termination")`
   returns the doc as top hit.

Optional manual test: upload the same file through the running API and view
in the React UI.

---

## 8. Risks & known limitations

| Risk | Mitigation |
|---|---|
| `llama3.1:8b` produces malformed JSON | Prompts already tolerate raw-text fallback (`_safe_parse_json`). Use temperature=0.1 and Ollama's `format="json"` option. |
| Cosmos `filters` SQL fragment not parseable | Support only the `c.<field> = '<value>'` shape; log & ignore anything else. |
| No OCR → scanned PDFs return empty text | Documented in RUNNING-OFFLINE.md; opt-in Tesseract can be added later. |
| Existing Cosmos vector index (1536-d) incompatible with 384-d Chroma | Chroma is standalone; no migration needed. |
| Windows path issues in ChromaDB | Use absolute paths derived from `Path(settings.chroma_path).resolve()`. |
| Long-lived Ollama first-token latency on cold model | Ollama keeps the model resident; the first request warms it. |
| `services/__init__.py` re-exports Azure classes at import time | Azure SDKs remain installed via `[project.dependencies]`; imports succeed even in local mode. |
| `SearchExecutor` type hint is `SearchService` not `SearchProtocol` | Duck typing at runtime — works. Widening is optional and left out of this cut. |
| `sentence-transformers` first run downloads ~90 MB model | Cached to `~/.cache/huggingface`; document in RUNNING-OFFLINE.md; can be pre-downloaded. |
| `chromadb>=0.5` pulls a large transitive tree (incl. `onnxruntime`) | Acceptable one-time install cost. Alternative `chromadb-client` requires a server — we want fully embedded. |

---

## 9. Out of scope (initial cut)

- Streaming SSE-style LLM output (analysis is one-shot per task).
- MCP server offline support beyond the LLM caller swap — the tools reuse the
  same registry/prompt code, so `summarize`, `extract_clauses`,
  `check_compliance` will work once the LLM caller is Ollama.
- Terraform / azd deprecation — infra stays for the Azure path.
- Auth (`AUTH_MODE`) — defaults to `none` when `backend=local`; the current
  `api_key` default (which requires Key Vault) is disabled for local runs.
- **Offline Docker image** — `Dockerfile` stays as the Azure production
  image. Local run is `make dev-offline` on bare metal.
- **Foundry-hosted workflow** (`agents/orchestrator/agent_workflow.py`) is
  not wired for local mode. The default `DocumentPipeline` covers the
  offline path.
- Pre-downloading the sentence-transformers model into `./data/` (users
  fetch on first run from HuggingFace).

---

## 10. Execution order (once approved)

1. Settings + factory skeleton + `.env.local.template`.
2. `LocalBlobStorage` + `SQLiteStore` (easy wins, testable in isolation).
3. `ChromaSearchService` (+ sentence-transformers embedder).
4. `LocalExtractor` (+ dataclass matching current DI result shape; TXT/PDF/DOCX/XLSX).
5. `OllamaCaller`.
6. Wire factory into `dependencies.py`, `documents.py` (`_build_pipeline`
   *and* the FAILED-status fallback), `search.py`, `events.py`, `mcp/server.py`.
7. Update `health.py` `/ready` with local checks (SQLite, Chroma, Ollama ping).
8. `pyproject.toml` extras + Makefile targets (`install-offline`, `dev-offline`).
9. `RUNNING-OFFLINE.md`.
10. Smoke test in `tests/offline/`.

Total: **8 new files, ~7 modified files** (up from 5 after gap review).
No agent, prompt, orchestrator, or doc-type YAML changes.

---

## 11. Gaps closed during re-verification

Before touching code, I re-scanned every file that touches Azure. The
following extra items were **missing from the first draft** and are now
folded into sections 3–5 above:

1. ✅ `/ready` endpoint (`health.py`) hits Cosmos + Blob + Azure OpenAI —
   needs local checks.
2. ✅ `/events` and WebSocket endpoint (`events.py`) instantiates
   `CosmosService` directly and reaches into `_container`.
3. ✅ MCP server (`mcp/server.py`) has its own hardcoded Azure OpenAI
   `_get_llm_caller`.
4. ✅ The FAILED-status fallback in `documents.py._run_pipeline_background`
   also instantiates `CosmosService()` directly.
5. ✅ Sample corpus is `.txt` files — local extractor must handle plain
   text (PyMuPDF alone would reject them).
6. ✅ `auth_mode` default of `api_key` requires Key Vault — needs to
   default to `none` for local.
7. ✅ `tracing.py` is *already* a no-op when App Insights connection string
   is empty (verified) — no code change, just docs.
8. ℹ️ `SearchExecutor` type-hint on `SearchService` (Azure AI Search
   wrapper) is duck-typed at runtime; documented as an optional cleanup.
9. ℹ️ `agents/orchestrator/agent_workflow.py` (Foundry variant) and
   `services/cosmos_vector_setup.py` are not on the default path;
   documented as untouched.

Everything else in the original plan holds.
