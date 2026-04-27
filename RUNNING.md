# DocuMind — Running & Testing Guide

## Prerequisites

| Requirement | Version | Check |
|-------------|---------|-------|
| Python | >= 3.11 | `python --version` |
| Terraform | >= 1.6.0 | `terraform --version` |
| Azure CLI | latest | `az --version` |
| Active Azure subscription | — | `az account show` |

---

## 1. Clone & Set Up Python Environment

```bash
# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# Install all dependencies (core + dev)
pip install -e ".[dev]"
```

---

## 2. Provision Azure Infrastructure

All infrastructure is codified in Terraform under the `infra/` directory.

```bash
cd infra

# Initialise Terraform (downloads providers)
terraform init

# Preview what will be created
terraform plan -var-file="environments/dev.tfvars"

# Deploy (creates ~17 Azure resources)
terraform apply -var-file="environments/dev.tfvars" -auto-approve
```

**Resources provisioned** (all in `rg-documind-dev`, `eastus2`):

| Resource | Name |
|----------|------|
| AI Services (GPT-4o + embeddings) | `documind-dev-aoai` |
| Document Intelligence | `documind-dev-di` |
| Blob Storage (3 containers) | `documinddevst` |
| Cosmos DB (serverless, 3 containers) | `documind-dev-cosmos` |
| Key Vault | `documind-dev-kv` |
| Log Analytics + App Insights | `documind-dev-law` / `documind-dev-appi` |

---

## 3. Configure the `.env` File

After Terraform completes, populate the `.env` file with connection details. Run these commands from the `infra/` directory:

```bash
# Get endpoints from Terraform outputs
terraform output

# Get keys from Azure CLI
az cosmosdb keys list --name documind-dev-cosmos --resource-group rg-documind-dev --query "primaryMasterKey" -o tsv
az cognitiveservices account keys list --name documind-dev-di --resource-group rg-documind-dev --query "key1" -o tsv
az storage account show-connection-string --name documinddevst --resource-group rg-documind-dev --query "connectionString" -o tsv
```

Your `.env` file (in the project root) should contain:

```env
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://documind-dev-aoai.openai.azure.com/

# Document Intelligence
AZURE_DOC_INTELLIGENCE_ENDPOINT=https://documind-dev-di.cognitiveservices.azure.com/
AZURE_DOC_INTELLIGENCE_KEY=<key from az cognitiveservices ...>

# Blob Storage
AZURE_STORAGE_ACCOUNT_NAME=documinddevst
AZURE_STORAGE_CONNECTION_STRING=<connection string from az storage ...>

# Cosmos DB
AZURE_COSMOS_ENDPOINT=https://documind-dev-cosmos.documents.azure.com:443/
AZURE_COSMOS_DATABASE=documind
AZURE_COSMOS_KEY=<key from az cosmosdb ...>

# Key Vault
AZURE_KEYVAULT_URL=https://documind-dev-kv.vault.azure.net/

# App Insights
APPLICATIONINSIGHTS_CONNECTION_STRING=<from terraform output>

# Local dev settings
AUTH_MODE=none
```

> **Note:** The `.env` file is in `.gitignore` — secrets are never committed.

---

## 4. Run Unit Tests (No Cloud Required)

All 140 tests run with mocked Azure services — no credentials needed.

```bash
# From the project root
python -m pytest -v --tb=short
```

Expected output:
```
140 passed, 0 failed
```

To run only the API tests:
```bash
python -m pytest tests/test_api.py tests/test_api_auth.py -v
```

---

## 5. Test End-to-End with a Real Document

### Option A: CLI Pipeline Script (Recommended First Test)

The CLI script runs the full pipeline synchronously and prints results to the console.

```bash
python scripts/test_pipeline.py <path-to-document> <doc_type>
```

**Supported document types:** `rfp`, `contract`, `spec`

**Supported file formats:** PDF, DOCX, XLSX, PPTX, PNG, JPG, TIFF

**Examples:**

```bash
# Test with an RFP document
python scripts/test_pipeline.py "samples/sample-rfp.pdf" rfp

# Test with a contract
python scripts/test_pipeline.py "C:\Documents\my-contract.pdf" contract

# Test with a technical specification
python scripts/test_pipeline.py spec-document.docx spec
```

**What the script does (4 stages):**

```
1. Ingestion   → Classifies doc type, uploads to Blob Storage
2. Extraction  → Runs Azure Document Intelligence (OCR, tables, key-values)
3. Analysis    → Sends extracted text to GPT-4o for summary, risks, clauses
4. Indexing    → Stores results in Cosmos DB with vector embeddings
```

**Sample output:**

```
============================================================
  DocuMind Pipeline Test
  File: sample-rfp.pdf (245,832 bytes)
  Doc type hint: rfp
============================================================

[OK] Doc-type registry loaded (3 types)
[OK] Blob Storage connected
[OK] Document Intelligence connected
[OK] Cosmos DB connected
[OK] Vector Search connected
[OK] Prompt templates loaded
[OK] Azure OpenAI connected

────────────────────────────────────────────────────────────
Running pipeline...
────────────────────────────────────────────────────────────

============================================================
  PIPELINE RESULTS
============================================================
  Document ID:      a1b2c3d4-...
  Status:           completed
  Stages completed: ingestion, extraction, analysis, search

  ── Extraction ──
  Doc type:    rfp
  Pages:       12
  Confidence:  0.94
  KV pairs:    8
  Tables:      3
  Text length: 15,234 chars

  ── Analysis ──
  Summary:
    This RFP seeks a vendor for building a cloud-based document
    processing platform with AI capabilities...

  Risks (3):
    [HIGH] Tight timeline
      Only 30 days for proposal submission
      → Start preparation immediately
    [MEDIUM] Budget constraints
      Budget range below market average
      → Propose phased delivery approach
============================================================
```

### Option B: FastAPI Server + Swagger UI

Start the API server, then interact via browser or `curl`.

#### Step 1: Start the server

```bash
python -m uvicorn documind.api.main:app --host 127.0.0.1 --port 8000 --reload
```

#### Step 2: Open Swagger UI

Navigate to **http://127.0.0.1:8000/docs** in your browser.

You'll see all endpoints documented with request/response schemas. Use the "Try it out" button on any endpoint.

#### Step 3: Test via curl

```bash
# Health check
curl http://127.0.0.1:8000/health

# Readiness check (verifies Azure connectivity)
curl http://127.0.0.1:8000/ready

# Upload a document (returns 202 — processing runs in background)
curl -X POST http://127.0.0.1:8000/documents \
  -F "file=@my-document.pdf" \
  -F "doc_type=rfp"

# Check processing status (use the document_id from the upload response)
curl http://127.0.0.1:8000/documents/{document_id}?doc_type=rfp

# Get analysis results (after processing completes)
curl http://127.0.0.1:8000/documents/{document_id}/analysis?doc_type=rfp

# Semantic search across processed documents
curl -X POST http://127.0.0.1:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "submission deadline", "top": 5}'
```

### API Endpoints Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness probe — always returns 200 |
| `GET` | `/ready` | Readiness probe — checks Cosmos, Blob, OpenAI |
| `POST` | `/documents` | Upload a document (multipart form) |
| `GET` | `/documents/{id}?doc_type=` | Get processing status |
| `GET` | `/documents/{id}/analysis?doc_type=` | Get extraction + analysis results |
| `POST` | `/search` | Semantic search across indexed documents |
| `WS` | `/documents/{id}/ws` | WebSocket for live pipeline updates |
| `GET` | `/documents/{id}/events` | SSE stream for pipeline updates |

---

## 6. Verify in Azure Portal

After a successful pipeline run, you can verify the data was stored:

### Blob Storage
1. Go to **Azure Portal → Storage accounts → documinddevst**
2. Open **Containers → raw-documents**
3. You should see a folder named with the document ID containing the uploaded file

### Cosmos DB
1. Go to **Azure Portal → Azure Cosmos DB → documind-dev-cosmos**
2. Open **Data Explorer → documind → documents**
3. Find the document record with extraction and analysis results

### App Insights (Tracing)
1. Go to **Azure Portal → Application Insights → documind-dev-appi**
2. Open **Transaction search** or **Performance**
3. Look for `document.pipeline` spans with per-stage breakdown

---

## 7. Troubleshooting

### "Unsupported file extension '.txt'"
The pipeline only accepts: **PDF, DOCX, XLSX, PPTX, PNG, JPG, TIFF**. Convert your document to PDF first.

### "No enabled doc type accepts format..."
The file format is supported but no doc-type config handles it. Check `src/documind/doctypes/types/` for registered types.

### Authentication errors connecting to Azure OpenAI
The pipeline uses `DefaultAzureCredential` for OpenAI (managed identity / Azure CLI). Make sure you're logged in:
```bash
az login
az account set --subscription "your-subscription-name"
```

### Cosmos DB / Blob Storage connection errors
Verify the keys in `.env` are current. Keys can be rotated — re-run the `az` commands from Step 3 if needed.

### "Module not found" errors
Make sure you installed in editable mode:
```bash
pip install -e ".[dev]"
```

### Port 8000 already in use
```bash
# Use a different port
python -m uvicorn documind.api.main:app --port 8001
```
