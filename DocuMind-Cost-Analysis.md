# DocuMind — Azure Cost Analysis

> Decision: Replace Azure AI Search (Standard tier, ~$250/month fixed) with **Cosmos DB vector search** (serverless, pay-per-request) to eliminate the largest fixed cost component.

---

## Per-Document Cost: 100-Page RFP

| Stage | Azure Service | What Happens | Units | Unit Price | Cost |
|-------|--------------|-------------|-------|-----------|------|
| **Ingestion** | Blob Storage | Upload ~8 MB PDF | 1 write + 8 MB stored | $0.05/10K ops + $0.018/GB | **~$0.001** |
| **Extraction** | Document Intelligence (Layout) | OCR + table/KV extraction on all 100 pages | 100 pages | $0.01/page | **$1.00** |
| **Analysis — Summarize** | GPT-4o | Send extracted text (~100K tokens) + prompt | ~100K input + ~2K output | $2.50/1M in, $10/1M out | **$0.27** |
| **Analysis — Extract Clauses** | GPT-4o | Same text, clause extraction prompt | ~100K input + ~3K output | same | **$0.28** |
| **Analysis — Identify Risks** | GPT-4o | Same text, risk identification prompt | ~100K input + ~2K output | same | **$0.27** |
| **Embedding** | text-embedding-3-small | Vectorize extracted text for search | ~100K tokens | $0.02/1M tokens | **$0.002** |
| **Indexing** | Cosmos DB (serverless) | Store record + vector index | ~50 RU | $0.25/1M RU | **~$0.00** |
| **State Tracking** | Cosmos DB (serverless) | Status updates (4 stage transitions) | ~20 RU | $0.25/1M RU | **~$0.00** |
| **Secrets** | Key Vault | Read API keys/connection strings | ~5 reads | $0.03/10K ops | **~$0.00** |
| **Observability** | App Insights | Trace/log data (~10 KB) | 10 KB | Free tier (5 GB/mo) | **$0.00** |

### Per-Document Totals

| Document Size | Doc Intelligence | GPT-4o (3 tasks) | Other | **Total** |
|--------------|-----------------|-------------------|-------|-----------|
| **10-page contract** | $0.10 | ~$0.82 | ~$0.00 | **≈ $0.92** |
| **50-page spec** | $0.50 | ~$0.82 | ~$0.00 | **≈ $1.32** |
| **100-page RFP** | $1.00 | ~$0.82 | ~$0.00 | **≈ $1.82** |
| **100-page RFP (with chunking)** | $1.00 | ~$1.60 | ~$0.00 | **≈ $2.60** |

> Note: GPT-4o cost is roughly similar for 10–100 pages because shorter documents produce fewer tokens but the prompt overhead is constant. Chunking (Phase 2) roughly doubles GPT-4o cost for large documents due to per-chunk calls + merge.

---

## Monthly Infrastructure (Fixed Costs)

| Resource | Tier | Monthly Cost | Notes |
|----------|------|-------------|-------|
| Cosmos DB | Serverless | **$0** fixed | Pay-per-RU only, no idle cost |
| Blob Storage | Standard LRS | **~$1** | Minimal at dev/demo volumes |
| Key Vault | Standard | **~$0** | Per-operation pricing only |
| App Insights | Free tier | **$0** | First 5 GB/month free |
| Document Intelligence | S0 | **$0** fixed | Pay-per-page only |
| Azure OpenAI | Pay-per-token | **$0** fixed | No idle cost |
| Container Apps | Consumption | **$0** idle | Pay only when processing |
| AI Foundry Project | — | **$0** | Management plane, no charge |
| ~~AI Search Standard~~ | ~~Removed~~ | ~~$250/mo saved~~ | Replaced by Cosmos DB vector search |
| **Monthly idle cost** | | **≈ $1–2** | |

---

## Volume Projections

| Volume | Avg Pages/Doc | Doc Intelligence | GPT-4o | Other | **Monthly Total** |
|--------|--------------|-----------------|--------|-------|-------------------|
| 10 docs/month (dev) | 50 | ~$5 | ~$4 | ~$1 | **≈ $10** |
| 50 docs/month (pilot) | 50 | ~$25 | ~$20 | ~$1 | **≈ $50** |
| 200 docs/month (production) | 50 | ~$100 | ~$80 | ~$2 | **≈ $185** |
| 500 docs/month (scale) | 50 | ~$250 | ~$200 | ~$5 | **≈ $460** |

---

## Cost Distribution

```
Document Intelligence  ████████████████████  55%
GPT-4o                 ████████████████      45%
Everything else        ▏                     <1%
```

The two cost drivers are **Document Intelligence** (per-page OCR) and **GPT-4o** (per-token analysis). All other services are effectively free at accelerator scale.

---

## AI Search vs Cosmos DB Vector Search — Decision

| Factor | AI Search (Standard) | Cosmos DB Vector Search (Serverless) |
|--------|---------------------|--------------------------------------|
| **Fixed cost** | ~$250/month | $0 |
| **Per-query cost** | Included in tier | ~$0.25/1M RU (~$0.00 per query) |
| **Vector search** | ✅ (HNSW) | ✅ (DiskANN) |
| **Full-text search** | ✅ | ✅ |
| **Semantic ranker** | ✅ (extra cost) | ❌ (use embedding similarity instead) |
| **Skillsets/Enrichment** | ✅ | ❌ (handled by our pipeline instead) |
| **Already provisioned** | Terraform module exists | Terraform module exists (serverless) |
| **Scaling** | Tier upgrades ($500+/mo) | Linear with usage |

**Decision:** Use Cosmos DB vector search for dev/pilot/production. AI Search can be re-introduced as an optional premium module for clients who need built-in skillsets or semantic ranker capabilities.

---

## Cost Optimization Levers (Future)

| Optimization | Savings | Trade-off |
|-------------|---------|-----------|
| **GPT-4o-mini** for low-risk tasks | ~10x cheaper per token | Slightly lower quality on complex analysis |
| **Response caching** | Skip re-analysis for unchanged docs | Cache invalidation complexity |
| **Selective analysis** | Only run relevant tasks per doc type | Fewer insights for some doc types |
| **Prebuilt DI models** | $0.01/page (vs $0.05 custom) | Less accurate for specialized formats |
| **Batch API** for GPT-4o | 50% discount | Higher latency (24h window) |
| **Reserved capacity** | Up to 30% for Document Intelligence | Commitment required |
