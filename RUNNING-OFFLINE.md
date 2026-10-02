# Running DocuMind Offline (No Azure Required)

DocuMind ships with a fully offline execution mode that replaces every
Azure dependency with a local equivalent.  Switching modes is done via a
single environment variable — no code changes are needed.

| Concern              | Azure mode                     | Offline mode                          |
| -------------------- | ------------------------------ | ------------------------------------- |
| LLM                  | Azure OpenAI                   | [Ollama](https://ollama.com) (`llama3.1:8b`) |
| Embeddings           | `text-embedding-3-large`       | `sentence-transformers/all-MiniLM-L6-v2` (384-d, CPU) |
| Vector search        | Cosmos DB for NoSQL (vector)   | ChromaDB (persistent, embedded)       |
| Metadata store       | Cosmos DB                      | SQLite (`./data/documind.sqlite`)     |
| Blob storage         | Azure Blob Storage             | Local filesystem (`./data/blobs/`)    |
| Document extraction  | Azure Document Intelligence    | PyMuPDF + python-docx + openpyxl      |
| Auth                 | Entra ID (JWT)                 | Disabled (`AUTH_MODE=none`)           |

> **Not supported offline**: OCR of scanned/image-only PDFs.  PDFs that
> contain no embedded text will yield empty content.  Everything else
> (text PDFs, DOCX, XLSX, TXT, MD) is fully supported.

---

## 1. Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for the web UI, optional)
- **[Ollama](https://ollama.com/download)** running locally

The very first request will also download the sentence-transformers
model (`~90 MB`) into `~/.cache/huggingface/`.  Subsequent runs use the
cache and stay fully offline.

---

## 2. Install

```powershell
# Windows PowerShell
git clone <your-repo> documind
cd documind

# Creates .venv and installs base + offline extras
make install-offline
```

Then pull the default LLM:

```powershell
ollama pull llama3.1:8b
```

*(Any Ollama chat model works — set `OLLAMA_MODEL` in `.env` to use a
different one, e.g. `mistral`, `qwen2.5:7b`, `phi3`.)*

---

## 3. Configure

Copy the offline template:

```powershell
Copy-Item .env.local.template .env
```

Key settings (see `.env.local.template` for full list):

```env
BACKEND=local
AUTH_MODE=none
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
LOCAL_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CHROMA_PATH=./data/chroma
SQLITE_PATH=./data/documind.sqlite
LOCAL_BLOB_DIR=./data/blobs
```

The `./data/` directory is created on first run.

---

## 4. Run

Start the API and the web UI together:

```powershell
make dev-offline
```

- API:  http://localhost:8000  (`/docs` for the OpenAPI UI, `/ready` for a health check)
- Web:  http://localhost:3000

To run only the API:

```powershell
$env:BACKEND = "local"
make run
```

---

## 5. Try It

Upload one of the bundled samples:

```powershell
curl.exe -F "file=@samples/contracts/software-license-agreement.txt" `
         -F "doc_type=contract" `
         http://localhost:8000/api/v1/documents/upload
```

Poll the returned `document_id`:

```powershell
curl.exe http://localhost:8000/api/v1/documents/<document_id>
```

Search semantically:

```powershell
curl.exe -X POST http://localhost:8000/api/v1/search/semantic `
  -H "Content-Type: application/json" `
  -d '{"query":"license termination","top":5}'
```

---

## 6. Switching Back to Azure

Just set `BACKEND=azure` (or delete it — Azure is the historical
default when Azure endpoints are configured).  No re-install needed;
the Azure code path is untouched.

```env
BACKEND=azure
AUTH_MODE=entra_id
AZURE_OPENAI_ENDPOINT=...
AZURE_COSMOS_ENDPOINT=...
# etc.
```

---

## 7. Troubleshooting

| Symptom                                       | Likely cause / fix                                                 |
| --------------------------------------------- | ------------------------------------------------------------------ |
| `/ready` reports `ollama: error`              | Ollama not started, or wrong `OLLAMA_BASE_URL`. Run `ollama serve`. |
| `Model not found` in Ollama logs              | `ollama pull llama3.1:8b` (or whatever `OLLAMA_MODEL` is set to).  |
| First upload takes 30–60 s                    | Sentence-transformers model download; only happens once.           |
| Search returns nothing                        | Check `data/chroma/` exists and the doc reached `COMPLETED` state. |
| PDF extraction returns empty content          | PDF is image-only. Offline mode does not include OCR.              |
| `sqlite3.OperationalError: database is locked`| Multiple processes writing at once. Restart the API.               |

---

## 8. What's Where

```
./data/
├── chroma/           # ChromaDB persistent store (vector index)
├── documind.sqlite   # SQLite metadata DB (document records)
└── blobs/            # Uploaded document originals
    └── documents/
        └── <document_id>/
            └── <filename>
```

Delete the whole `./data/` directory to reset the offline install.

---

## 9. Configuration Reference

See `src/documind/core/config/settings.py` for the full list.  The
offline-only fields are:

- `backend` — `"local"` or `"azure"`
- `auth_mode` — `"none"`, `"api_key"`, or `"entra_id"`
- `chroma_path` / `chroma_collection`
- `sqlite_path`
- `local_blob_dir`
- `ollama_base_url` / `ollama_model` / `ollama_timeout_seconds`
- `local_embedding_model` / `local_embedding_dim`
