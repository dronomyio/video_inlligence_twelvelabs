# API.md — All 47 Endpoints

Base URL: `http://localhost:8000`
Swagger UI: `http://localhost:8000/docs`

## Authentication

Three endpoints require x402 USDC payment when `X402_ENFORCE_PAYMENT=true`:
- `POST /search/semantic`
- `POST /campaigns/match`
- `POST /trends/detect`

Add header: `X-Payment-Transfer-Id: {transfer_id}`
Demo mode: `X-Payment-Transfer-Id: sim_anything` always passes.

---

## Pipeline

| Method | Path | Description |
|--------|------|-------------|
| POST | `/pipeline/start` | Start 500-video ingestion |
| GET | `/pipeline/status` | Queue depth + graph stats |
| GET | `/pipeline/job/{job_id}` | RQ job status |

## Graph

| Method | Path | Description |
|--------|------|-------------|
| GET | `/graph/stats` | Node counts for all 13 types |
| GET | `/videos` | Paginated list. Params: `skip`, `limit`, `category` |
| GET | `/videos/{video_id}/similar` | Similar via SIMILAR_TO edges |
| GET | `/categories` | All 5 categories with counts |

## Search Track

| Method | Path | Notes |
|--------|------|-------|
| POST | `/search/semantic` | **x402.** Body: `{query, category?, limit?, use_twelvelabs?}` |
| GET | `/search/top-hooks` | Params: `category`, `limit` |
| GET | `/search/product-moments` | **x402.** |

## Segmentation Track

| Method | Path | Description |
|--------|------|-------------|
| GET | `/segment/video/{video_id}` | All scenes ordered by t_start |
| GET | `/segment/ad-breaks` | Optimal insertions. Params: `category`, `min_score`, `limit` |
| GET | `/segment/structure-analysis` | Hook/Build/Payoff/CTA distribution |

## Compliance Track

| Method | Path | Description |
|--------|------|-------------|
| GET | `/compliance/flags` | Params: `severity`, `category`, `limit` |
| GET | `/compliance/summary` | Counts by severity + rule type |
| POST | `/compliance/check/{video_id}` | On-demand Pegasus check |

## Briefs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/briefs` | Params: `min_cpm`, `category`, `limit` |
| GET | `/briefs/{video_id}` | Single brief. 404 if none. |

## Ontology (Opus 4.6)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ontology/infer` | Opus → Cypher schema patch |
| GET | `/ontology/schema` | Node labels + relationship types |
| GET | `/ontology/viral-formats` | ViralFormat nodes |

## Campaigns (Opus 4.6)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/campaigns/match` | **x402.** Body: `{name, advertiser, vertical, target_audience, budget_usd, max_cpm, activate_on_networks, networks}` |
| GET | `/campaigns` | All campaigns |
| GET | `/campaigns/{campaign_id}` | Campaign + placements |

## Ad Network Deals

| Method | Path | Description |
|--------|------|-------------|
| POST | `/deals/activate/{video_id}` | Params: `networks` (gam,ttd) |
| GET | `/deals` | Params: `platform`, `status` |
| GET | `/revenue` | Total + by platform |
| GET | `/revenue/deals/{deal_id}/refresh` | Params: `platform` |

## LTX Creatives

| Method | Path | Description |
|--------|------|-------------|
| POST | `/creatives/generate/{video_id}` | Params: `ad_format` (6s_bumper/15s_preroll/thumbnail) |
| POST | `/creatives/campaign/{campaign_id}` | Params: `ad_format` |
| GET | `/creatives/video/{video_id}` | List creatives |

## TrackIt Workflow

| Method | Path | Description |
|--------|------|-------------|
| POST | `/trackit/workflow/{video_id}` | Submit to state machine |
| GET | `/trackit/workflow/{workflow_id}/status` | Progress % + completed states |
| POST | `/trackit/mam/{video_id}` | Push SMPTE ST 2067 metadata |
| GET | `/trackit/audit` | Params: `video_id`, `limit` |
| GET | `/trackit/qoe/{video_id}` | QoE score + VMAF estimate |
| GET | `/trackit/pipeline-states` | 8 canonical state names |

## Circle / x402

| Method | Path | Description |
|--------|------|-------------|
| GET | `/circle/wallet` | USDC balance |
| POST | `/circle/payment-intent` | Params: `query_type` |
| GET | `/circle/verify/{transfer_id}` | Params: `query_type` |
| GET | `/circle/transactions` | Params: `limit` |
| GET | `/x402/stats` | Revenue by query type |
| GET | `/x402/pricing` | Prices + enforcement status |
| GET | `/.well-known/mcp.json` | MCP manifest |

## Trends + Health

| Method | Path | Description |
|--------|------|-------------|
| POST | `/trends/detect` | **x402.** Opus trend detector |
| GET | `/health` | `{"status": "ok"}` |
| GET | `/` | Platform info |

---

## Pattern: adding a new endpoint

```python
# backend/main.py
@app.get("/new/endpoint")
async def new_endpoint(param: str = "", request: Request = None):
    gate_resp = await x402_gate.gate(request, "semantic_search")  # if paid
    if gate_resp:
        return gate_resp
    with db.driver.session() as s:
        recs = s.run("MATCH (v:Video) RETURN v LIMIT 10")
        return {"results": [dict(r) for r in recs]}

# frontend/src/api.js — add:
newEndpoint: (param) => API.get('/new/endpoint', { params: { param } }),
```
