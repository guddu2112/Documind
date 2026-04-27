"""Quick test: upload RFP file and poll for completion."""
import httpx
import json
import time

BASE = "http://127.0.0.1:8003"
FILE_PATH = r"D:\EPAM\ai ideas\aiaccelerator\RFP - HWTE SN3.0 PRD_0124.pdf"

# Upload
with open(FILE_PATH, "rb") as f:
    resp = httpx.post(
        f"{BASE}/documents",
        files={"file": ("RFP - HWTE SN3.0 PRD_0124.pdf", f, "application/pdf")},
        data={"doc_type": "rfp"},
        timeout=30.0,
    )

print("Upload status:", resp.status_code)
result = resp.json()
print(json.dumps(result, indent=2))
doc_id = result.get("document_id", "")
doc_type = result.get("doc_type", "rfp")

# Poll for completion — try both the initial and resolved partition keys
for i in range(60):
    time.sleep(5)
    # Try with the original doc_type first, then cross-partition fallback
    status_resp = httpx.get(
        f"{BASE}/documents/{doc_id}",
        timeout=10.0,
    )
    status_data = status_resp.json()
    current = status_data.get("status", "unknown")
    doc_type_resolved = status_data.get("doc_type", doc_type)
    print(f"Poll {i+1}: status={current} doc_type={doc_type_resolved}")
    if current in ("completed", "failed"):
        print(json.dumps(status_data, indent=2))
        break

# Fetch analysis results
if current == "completed":
    analysis_resp = httpx.get(
        f"{BASE}/documents/{doc_id}/analysis?doc_type={doc_type_resolved}",
        timeout=10.0,
    )
    print("\n=== ANALYSIS RESULTS ===")
    print(json.dumps(analysis_resp.json(), indent=2))
