# DocuMind — Sample Documents

This directory contains sample documents for testing, demoing, and validating the DocuMind pipeline. Each document type has its own folder with source documents and expected extraction/analysis outputs.

## Document Types

| Type | Folder | Count | Description |
|------|--------|-------|-------------|
| **RFP** | `rfps/` | 2 | Requests for Proposal — procurement documents with requirements, evaluation criteria, budgets |
| **Contract** | `contracts/` | 2 | Professional services and software license agreements with clauses, obligations, terms |
| **Spec** | `specs/` | 2 | Technical specifications with functional/non-functional requirements, acceptance criteria |

## Directory Structure

```
samples/
├── README.md
├── rfps/
│   ├── cloud-migration-rfp.txt
│   ├── data-analytics-rfp.txt
│   └── expected/
│       ├── cloud-migration-rfp.json
│       └── data-analytics-rfp.json
├── contracts/
│   ├── professional-services-agreement.txt
│   ├── software-license-agreement.txt
│   └── expected/
│       ├── professional-services-agreement.json
│       └── software-license-agreement.json
└── specs/
    ├── payment-gateway-spec.txt
    ├── inventory-system-spec.txt
    └── expected/
        ├── payment-gateway-spec.json
        └── inventory-system-spec.json
```

## Quick Start

### Upload via API

```bash
# Upload a single document
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@samples/rfps/cloud-migration-rfp.txt" \
  -F "doc_type=rfp"

# Upload all RFPs
for f in samples/rfps/*.txt; do
  curl -X POST http://localhost:8000/documents/upload \
    -F "file=@$f" -F "doc_type=rfp"
done

# Upload all sample documents
for type in rfps:rfp contracts:contract specs:spec; do
  IFS=: read folder dtype <<< "$type"
  for f in samples/$folder/*.txt; do
    curl -X POST http://localhost:8000/documents/upload \
      -F "file=@$f" -F "doc_type=$dtype"
  done
done
```

### Upload via MCP

Use the `upload_document` MCP tool with any MCP-compatible client:

```json
{
  "tool": "upload_document",
  "arguments": {
    "file_path": "samples/rfps/cloud-migration-rfp.txt",
    "doc_type": "rfp"
  }
}
```

## Expected Outputs

Each `expected/` folder contains JSON files showing the expected extraction and analysis results for the corresponding source document. These serve as:

- **Demo reference** — show stakeholders what DocuMind produces
- **Validation baseline** — compare actual pipeline output against expected results
- **Test fixtures** — use in automated tests to verify extraction accuracy

### Output Structure

Every expected output JSON follows this structure:

```json
{
  "document_type": "rfp | contract | spec",
  "source_file": "filename.txt",
  "extraction": { ... },
  "analysis": { ... }
}
```

The `extraction` fields match the document type's configured `extraction_fields` in `src/documind/doctypes/types/<type>.yaml`.

The `analysis` section contains the output of the configured analysis task (summarize, extract_clauses, or compliance_check).

## Sample Summaries

### RFPs

| Document | Organization | Budget | Deadline |
|----------|-------------|--------|----------|
| Cloud Migration RFP | Northwind Traders | $1.5M–$2.5M | 2026-02-28 |
| Data Analytics RFP | Contoso Financial | $2M–$3.5M | 2026-03-28 |

### Contracts

| Document | Parties | Value | Term |
|----------|---------|-------|------|
| Professional Services Agreement | Alpine Solutions ↔ Woodgrove Bank | $650K | 12 months |
| Software License Agreement | Fabrikam Software ↔ Adventure Works | $600K/yr | 36 months |

### Specs

| Document | Author | Version | Requirements |
|----------|--------|---------|-------------|
| Payment Gateway API | Tailspin Toys | 2.1 | 10 FR + 10 NFR |
| Inventory Management System | Wide World Importers | 1.3 | 10 FR + 7 NFR |

## Notes

- All documents use **fictional companies** (Microsoft sample names) — safe for demos and public presentations.
- Documents are plain text (`.txt`). In production, DocuMind processes PDF, DOCX, and scanned images via Azure Document Intelligence.
- Expected outputs are approximate — actual LLM-generated extractions will vary in wording but should match on key facts and structure.
