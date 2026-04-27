# Adding a New Document Type in DocuMind

This guide walks through adding a new document type to the DocuMind pipeline, using **Invoice** as an example.

---

## Architecture Overview

DocuMind uses a **plugin-style, config-driven** document type system:

```
src/documind/doctypes/
├── types/             ← YAML configs (auto-discovered at startup)
│   ├── rfp.yaml
│   ├── contract.yaml
│   ├── spec.yaml
│   └── invoice.yaml   ← your new type goes here
├── registry.py        ← auto-loads all *.yaml from types/
└── schema.py          ← Pydantic validation for YAML structure
```

The pipeline **dynamically resolves** doc types at runtime — no hard-coded references to add or update.

---

## Step 1: Scaffold the New Type

Run the scaffolding command from the project root:

```bash
make add-doctype NAME=invoice DISPLAY="Invoice" TASKS="summarize" FORMATS="pdf docx xlsx"
```

This generates:

| File | Purpose |
|------|---------|
| `src/documind/doctypes/types/invoice.yaml` | Type configuration (fields, tasks, search mappings) |
| `src/documind/agents/analysis/prompts/invoice-summary.txt` | GPT-4o analysis prompt template |
| `samples/invoices/` | Directory for sample test documents |

**Available TASKS:** `summarize`, `extract_clauses`, `compliance_check`

**Available FORMATS:** `pdf`, `docx`, `pptx`, `xlsx`, `png`, `jpg`, `tiff`

---

## Step 2: Configure the YAML

Open `src/documind/doctypes/types/invoice.yaml` and customize it. Here is a complete example:

```yaml
name: invoice
display_name: "Invoice"
description: "Invoices, bills, and payment requests from vendors or service providers."
version: "1.0"
enabled: true

supported_formats:
  - pdf
  - docx
  - xlsx

# Azure Document Intelligence model to use for extraction.
# Options: prebuilt-layout (general), prebuilt-invoice (invoice-specific),
#          prebuilt-contract, prebuilt-receipt, prebuilt-tax.us.w2, etc.
doc_intelligence_model: prebuilt-invoice

# Structured fields to extract from the document.
# field_type options: text, date, currency, list, table, boolean
extraction_fields:
  - name: invoice_number
    label: "Invoice Number"
    field_type: text
    required: true
    description: "Unique invoice identifier"

  - name: vendor_name
    label: "Vendor Name"
    field_type: text
    required: true
    description: "Name of the issuing vendor or supplier"

  - name: invoice_date
    label: "Invoice Date"
    field_type: date
    required: true
    description: "Date the invoice was issued"

  - name: due_date
    label: "Due Date"
    field_type: date
    required: true
    description: "Payment due date"

  - name: total_amount
    label: "Total Amount"
    field_type: currency
    required: true
    description: "Total amount due including taxes"

  - name: subtotal
    label: "Subtotal"
    field_type: currency
    required: false
    description: "Amount before taxes"

  - name: tax_amount
    label: "Tax Amount"
    field_type: currency
    required: false
    description: "Total tax applied"

  - name: line_items
    label: "Line Items"
    field_type: table
    required: false
    description: "Itemized list of goods or services"

  - name: payment_terms
    label: "Payment Terms"
    field_type: text
    required: false
    description: "Payment conditions (e.g., Net 30, Net 60)"

  - name: purchase_order
    label: "Purchase Order Number"
    field_type: text
    required: false
    description: "Associated PO number, if any"

# Analysis tasks to run after extraction.
# Each task maps to a prompt template and a registered task handler.
analysis_tasks:
  - name: summarize
    prompt_template: invoice-summary.txt
    description: "Summarize invoice details, flag anomalies, and identify risks"

# Fields to index in Azure AI Search for semantic search.
search_field_mappings:
  - source_field: content
    index_field: content
    searchable: true
    filterable: false
    facetable: false

  - source_field: vendor_name
    index_field: vendor
    searchable: true
    filterable: true
    facetable: true

  - source_field: invoice_number
    index_field: title
    searchable: true
    filterable: true
    facetable: false

  - source_field: total_amount
    index_field: value
    searchable: false
    filterable: true
    facetable: false

  - source_field: invoice_date
    index_field: effective_date
    searchable: false
    filterable: true
    facetable: false

metadata: {}
```

### Key Configuration Decisions

| Setting | Recommendation |
|---------|---------------|
| `doc_intelligence_model` | Use `prebuilt-invoice` for invoices — it extracts vendor, amounts, line items natively. Use `prebuilt-layout` for generic document types. |
| `extraction_fields` | Define all fields you want structured output for. The pipeline maps DI results to these fields. |
| `analysis_tasks` | Each task needs a matching prompt template. Use existing task names (`summarize`, `extract_clauses`, `compliance_check`) or register new ones (see Step 5). |
| `search_field_mappings` | Map to existing Azure AI Search index fields (`content`, `title`, `vendor`, `value`, `effective_date`). |

---

## Step 3: Write the Analysis Prompt

Edit `src/documind/agents/analysis/prompts/invoice-summary.txt`:

```text
You are a financial document analyst. Analyze the following invoice document and produce a structured JSON response.

## Document Text
{{ document_text }}

## Instructions
1. Extract and verify all key financial details
2. Check for mathematical correctness (subtotal + tax = total)
3. Identify any anomalies, missing information, or risks
4. Flag duplicate charges or unusual line items

## Required JSON Output
{
  "vendor_summary": "Brief description of vendor and invoice purpose",
  "financial_summary": {
    "subtotal": "amount or null",
    "tax": "amount or null",
    "total": "amount",
    "currency": "USD/EUR/etc."
  },
  "line_item_count": 0,
  "payment_terms": "e.g., Net 30",
  "anomalies": [
    "Any mathematical errors, missing fields, or suspicious items"
  ],
  "risks": [
    {
      "title": "Risk title",
      "description": "What the risk is",
      "severity": "low|medium|high|critical",
      "clause_reference": null,
      "recommendation": "Suggested action"
    }
  ]
}
```

> **Tip:** The `{{ document_text }}` placeholder is required — it's rendered via Jinja2 with the full extracted text from Document Intelligence.

---

## Step 4 (Optional): Add a Typed Pydantic Model

For type-safe fields beyond the generic `ExtractionResult` and `AnalysisResult`, create a model file:

**`src/documind/core/models/invoice.py`**

```python
"""Invoice-specific result models."""

from __future__ import annotations

from pydantic import BaseModel


class InvoiceLineItem(BaseModel):
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None


class InvoiceExtractionResult(BaseModel):
    invoice_number: str | None = None
    vendor_name: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    subtotal: float | None = None
    tax_amount: float | None = None
    total_amount: float | None = None
    payment_terms: str | None = None
    purchase_order: str | None = None
    line_items: list[InvoiceLineItem] = []


class InvoiceAnalysisResult(BaseModel):
    vendor_summary: str | None = None
    financial_summary: dict | None = None
    line_item_count: int = 0
    anomalies: list[str] = []
```

This step is optional — the pipeline works with the generic models. Typed models help if you build invoice-specific API responses or downstream logic.

---

## Step 5 (Optional): Register a Custom Analysis Task

If the built-in tasks (`summarize`, `extract_clauses`, `compliance_check`) don't fit your needs, you can register a new one.

Edit or create a file in `src/documind/agents/analysis/` and use the `@register_task` decorator:

```python
from documind.agents.analysis.task_registry import register_task

@register_task("validate_invoice")
def validate_invoice(document_text: str, doc_type: str, task_config, **kwargs):
    """Custom task: cross-check line items against totals."""
    # Your custom logic here
    # Return dict with 'summary' and 'risks' keys
    return {
        "summary": "...",
        "risks": [],
    }
```

Then reference it in your YAML:

```yaml
analysis_tasks:
  - name: validate_invoice
    prompt_template: invoice-validation.txt
    description: "Validate invoice math and flag discrepancies"
```

---

## Step 6: Update the Web UI (Optional)

The Upload panel has a doc type selector. To add `invoice` as an option, edit `web/src/components/UploadPanel.tsx`:

```typescript
// Change this line:
const DOC_TYPES = ["auto", "rfp", "contract", "spec"] as const;

// To:
const DOC_TYPES = ["auto", "rfp", "contract", "spec", "invoice"] as const;
```

> **Note:** Even without this change, uploading with "Auto-detect" will work if the file format matches the `supported_formats` in your YAML.

---

## Step 7: Test

1. **Restart the API server** — the registry auto-discovers new YAML files on startup:
   ```bash
   make run
   ```

2. **Verify the type loaded** — check the server logs for:
   ```
   INFO [documind.doctypes.registry] Loaded doc-type: invoice (invoice.yaml)
   ```

3. **Upload a test invoice** via the Web UI or API:
   ```bash
   curl -X POST http://localhost:8000/documents \
     -F "file=@samples/invoices/sample-invoice.pdf" \
     -F "doc_type=invoice"
   ```

4. **Check pipeline progress:**
   ```bash
   curl http://localhost:8000/documents/<document_id>
   ```

5. **View analysis results:**
   ```bash
   curl http://localhost:8000/documents/<document_id>/analysis?doc_type=invoice
   ```

6. **Search indexed content:**
   ```bash
   curl -X POST http://localhost:8000/search \
     -H "Content-Type: application/json" \
     -d '{"query": "invoice total amount", "doc_type": "invoice"}'
   ```

---

## Quick Reference: What Goes Where

| What | Where | Required? |
|------|-------|-----------|
| YAML config | `src/documind/doctypes/types/invoice.yaml` | Yes |
| Analysis prompt | `src/documind/agents/analysis/prompts/invoice-summary.txt` | Yes |
| Sample documents | `samples/invoices/` | No |
| Typed Pydantic model | `src/documind/core/models/invoice.py` | No |
| Custom task handler | `src/documind/agents/analysis/` | No |
| Web UI doc type option | `web/src/components/UploadPanel.tsx` | No |

## What You Do NOT Need to Touch

- **API endpoints** — `doc_type` is a free-form string parameter
- **Pipeline / Orchestrator** — resolves tasks from YAML dynamically
- **Extraction agent** — reads `doc_intelligence_model` from YAML
- **Analysis agent** — dispatches tasks via `TaskRegistry`
- **Search agent** — uses `search_field_mappings` from YAML
- **Cosmos DB schema** — `doc_type` is already a partition key
