---
name: viral-intel-dev
version: 1.0.0
description: >
  Use this skill when working on the ViralIntel codebase — adding or changing
  API endpoints, writing Neo4j Cypher queries, working with backend services,
  adding React frontend pages, or understanding how any service integrates.
  Activate when the user mentions: endpoint, route, Cypher, Neo4j, service,
  TwelveLabs, ZeroClick, Opus, LTX, TrackIt, Circle, GAM, TTD, React page,
  component, or any ViralIntel backend/frontend file.
metadata:
  openclaw:
    requires:
      env:
        - TWELVELABS_API_KEY
        - ANTHROPIC_API_KEY
        - NEO4J_URI
        - NEO4J_USER
        - NEO4J_PASSWORD
      bins:
        - docker
        - python3
    primaryEnv: TWELVELABS_API_KEY
---

# ViralIntel — Development Skill

## Project layout

```
viral-intel-nab2026/
├── backend/          ← FastAPI, 14 Python files, 47 endpoints
├── frontend/         ← React 18, 10 pages
├── neo4j/init/       ← seed.cypher, init.sh
└── tests/            ← 65 integration tests
```

## Backend services map

| File | Class | Role |
|------|-------|------|
| `config.py` | `Settings` | All 40 env vars via pydantic-settings |
| `database.py` | `Neo4jDB` | All Neo4j read/write. Import: `from database import db` |
| `ingestion.py` | `VideoIngestionService` | YouTube + TikTok discovery |
| `twelvelabs_service.py` | `TwelveLabsService` | Marengo search + Pegasus segment/comply |
| `zeroclick_service.py` | `ZeroClickService` | Advertiser brief generation |
| `opus_service.py` | module functions | 3 Opus 4.6 jobs |
| `adnetwork_service.py` | `GAMService`, `TTDService`, `RevenueTracker` | Ad activation |
| `circle_x402_service.py` | `CircleWalletService`, `X402PaymentGate` | USDC payments |
| `ltx_service.py` | `LTXService` | AI video creative generation |
| `trackit_service.py` | `TrackItWorkflowEngine` | Pipeline orchestration + MAM |
| `worker.py` | RQ functions | Background ingestion jobs |
| `main.py` | FastAPI app | 47 endpoint handlers |

## All 47 API endpoints

**Pipeline:** POST /pipeline/start · GET /pipeline/status · GET /pipeline/job/{id}

**Graph:** GET /graph/stats · GET /videos · GET /videos/{id}/similar · GET /categories

**Search (x402):** POST /search/semantic · GET /search/top-hooks · GET /search/product-moments

**Segmentation:** GET /segment/video/{id} · GET /segment/ad-breaks · GET /segment/structure-analysis

**Compliance:** GET /compliance/flags · GET /compliance/summary · POST /compliance/check/{id}

**Briefs:** GET /briefs · GET /briefs/{video_id}

**Ontology:** POST /ontology/infer · GET /ontology/schema · GET /ontology/viral-formats

**Campaigns (x402):** POST /campaigns/match · GET /campaigns · GET /campaigns/{id}

**Deals:** POST /deals/activate/{id} · GET /deals · GET /revenue · GET /revenue/deals/{id}/refresh

**LTX:** POST /creatives/generate/{id} · POST /creatives/campaign/{id} · GET /creatives/video/{id}

**TrackIt:** POST /trackit/workflow/{id} · GET /trackit/workflow/{id}/status · POST /trackit/mam/{id} · GET /trackit/audit · GET /trackit/qoe/{id} · GET /trackit/pipeline-states

**Circle/x402:** GET /circle/wallet · POST /circle/payment-intent · GET /circle/verify/{id} · GET /circle/transactions · GET /x402/stats · GET /x402/pricing · GET /.well-known/mcp.json

**Trends (x402):** POST /trends/detect

**Health:** GET /health · GET /

## Pattern: adding a new endpoint

```python
# backend/main.py — add after the relevant section
@app.get("/new/endpoint")
async def new_endpoint(param: str = "", request: Request = None):
    # If paid: add x402 gate
    gate_resp = await x402_gate.gate(request, "semantic_search")
    if gate_resp:
        return gate_resp

    with db.driver.session() as s:
        recs = s.run("MATCH (v:Video) RETURN v LIMIT 10")
        return {"results": [dict(r) for r in recs]}

# frontend/src/api.js — add:
newEndpoint: (param) => API.get('/new/endpoint', { params: { param } }),
```

## Neo4j — 13 node types

| Node | Key properties |
|------|---------------|
| `:Video` | video_id, viral_score, hook_strength, view_count, category, platform, twelvelabs_video_id |
| `:Scene` | scene_id, t_start, t_end, segment_type, viral_segment_score, attention_score |
| `:Creator` | creator_id, name, platform, subscriber_count |
| `:Trend` | name, frequency, velocity |
| `:Category` | name, description |
| `:AdvertBrief` | headline, placement_moment, target_verticals, estimated_cpm, zeroclick_context |
| `:ComplianceFlag` | rule, severity, t_start, explanation |
| `:Campaign` | campaign_id, advertiser, budget_usd, match_score |
| `:AdDeal` | deal_id, platform, impressions, revenue_usd |
| `:ViralFormat` | name, pattern_description, avg_viral_score |
| `:Payment` | transfer_id, query_type, amount_usdc, chain |
| `:Creative` | creative_id, video_url, ad_format, duration, status |
| `:WorkflowEvent` | workflow_id, state, success, recorded_at |

## Common Cypher patterns

```cypher
-- Top viral videos in a category
MATCH (v:Video)
WHERE v.category = 'food_cooking' AND v.viral_score > 0.7
RETURN v.video_id, v.title, v.viral_score
ORDER BY v.viral_score DESC LIMIT 20

-- Hook segments with no critical flags
MATCH (sc:Scene)-[:SEGMENT_OF]->(v:Video)
WHERE sc.segment_type = 'hook'
  AND NOT EXISTS {
    MATCH (sc)-[:HAS_FLAG]->(f:ComplianceFlag)
    WHERE f.severity IN ['high','critical']
  }
RETURN v.video_id, sc.t_start, sc.viral_segment_score
ORDER BY sc.viral_segment_score DESC LIMIT 10

-- Revenue by platform
MATCH (d:AdDeal)
RETURN d.platform, sum(d.revenue_usd) as revenue, count(d) as deals
ORDER BY revenue DESC

-- x402 payment summary
MATCH (p:Payment)
RETURN p.query_type, count(p) as count, sum(p.amount_usdc) as total_usdc
```

## Pattern: adding a new Neo4j node type

```python
# 1. database.py — add constraint in init_schema()
s.run("CREATE CONSTRAINT new_id IF NOT EXISTS FOR (n:New) REQUIRE n.id IS UNIQUE")

# 2. database.py — add upsert method
def upsert_new(self, data: dict) -> None:
    with self.driver.session() as s:
        s.run("MERGE (n:New {id: $id}) SET n += {name: $name}", **data)

# 3. neo4j/init/seed.cypher — add seed data
MERGE (:New {id: 'seed_1', name: 'First item'});
```

## Frontend — adding a new React page

```javascript
// frontend/src/pages/NewPage.js
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../api';

export default function NewPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['new-data'],
    queryFn: () => api.getVideos({ limit: 10 }).then(r => r.data),
    refetchInterval: 15000,
  });

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">New Page</div>
        <div className="page-sub">Description</div>
      </div>
      <div className="metrics">
        <div className="metric-card">
          <div className="metric-label">Total</div>
          <div className="metric-val" style={{ color: 'var(--cyan)' }}>
            {data?.videos?.length ?? 0}
          </div>
        </div>
      </div>
    </div>
  );
}
```

Then in `App.js`: import, add to NAV array, add `<Route path="/newpath" element={<NewPage />} />`.

## CSS design tokens

```css
--bg: #080c10    --bg1: #0d1318   --bg2: #121920
--cyan: #00e5ff  --green: #00e87a  --amber: #ffb800
--purple: #7b61ff --pink: #ff6eb4  --teal: #00d4aa
--text: #ddeef8  --muted: #5a7a94  --mono: 'Courier New'
```

## Critical rules

1. All services fall back gracefully when their API key is absent — never remove fallback logic
2. x402 gate must be called at top of `/search/semantic`, `/campaigns/match`, `/trends/detect`
3. Neo4j writes use `MERGE` not `CREATE` — always idempotent
4. Always delete downloaded MP4 after TwelveLabs upload (`try/finally` in worker.py)
5. Check `settings.enable_gam` and `settings.enable_ttd` before any GAM/TTD call
