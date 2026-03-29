---
name: viral-intel-revenue
version: 1.0.0
description: >
  Use this skill for ViralIntel monetisation — configuring and debugging x402
  USDC micropayments, Circle Arc wallet, Google Ad Manager line items, The Trade
  Desk PMP deals, Opus campaign matching, LTX creative generation, and the MCP
  manifest for AI agent discovery. Activate when the user mentions: revenue,
  payment, USDC, Circle, x402, GAM, TTD, deal, campaign, Opus match, creative,
  LTX, MCP, advertiser, brief, CPM, or monetisation.
metadata:
  openclaw:
    requires:
      env:
        - ANTHROPIC_API_KEY
        - CIRCLE_API_KEY
        - CIRCLE_WALLET_ID
        - ENABLE_GAM
        - ENABLE_TTD
      bins:
        - docker
        - curl
    primaryEnv: ANTHROPIC_API_KEY
---

# ViralIntel — Revenue Skill

## Four stacked revenue layers

```
Layer 1: x402 USDC micropayments    per-query · Circle Arc · Arbitrum
Layer 2: ZeroClick.ai briefs        machine-readable placement cards
Layer 3: GAM + TTD deal activation  30–35% platform margin
Layer 4: Opus SaaS subscription     $500–$2K/month/seat
```

---

## Layer 1 — x402 USDC Micropayments

### Pricing

| Endpoint | Query type | Price |
|----------|-----------|-------|
| POST /search/semantic | semantic_search | $0.05 USDC |
| POST /campaigns/match | campaign_match | $0.50 USDC |
| POST /trends/detect | trend_detect | $0.25 USDC |
| GET /briefs/{id} | brief_lookup | $0.025 USDC |

### Enforce or demo mode

```bash
X402_ENFORCE_PAYMENT=false   # demo mode — gate always passes (default)
X402_ENFORCE_PAYMENT=true    # real mode — requires payment header
```

### Payment flow for AI agents

```
1. GET /.well-known/mcp.json       → discover tools + prices
2. POST /circle/payment-intent     → get USDC deposit address
3. Send USDC to deposit_address on Arbitrum
4. GET /circle/verify/{transfer_id} → confirm payment
5. Call paid endpoint with header: X-Payment-Transfer-Id: {transfer_id}
```

Demo shortcut: `X-Payment-Transfer-Id: sim_anything` always passes.

### Circle wallet setup

```bash
# .env
CIRCLE_API_KEY=your_key         # console.circle.com → API Keys
CIRCLE_WALLET_ID=wallet_xxx     # console.circle.com → Wallets → Create
CIRCLE_ENTITY_SECRET=secret     # shown once at wallet creation
CIRCLE_ENVIRONMENT=testnet      # testnet (free) or mainnet (real USDC)
```

### Check wallet + revenue

```bash
curl http://localhost:8000/circle/wallet       # USDC balance
curl http://localhost:8000/x402/stats          # revenue by query type
curl http://localhost:8000/x402/pricing        # current prices + enforcement
curl http://localhost:8000/circle/transactions # recent inflows
```

### Neo4j — payment records

```cypher
MATCH (p:Payment)
RETURN p.query_type, count(p) as count, sum(p.amount_usdc) as total
ORDER BY total DESC
```

---

## Layer 2 — ZeroClick.ai Briefs

Each indexed video gets a placement card:
```json
{
  "headline": "Warm food content — 1.8M views. Ideal for CPG, kitchenware.",
  "placement_moment": 12.1,
  "target_verticals": ["CPG", "kitchenware"],
  "estimated_cpm": 4.15,
  "zeroclick_context": "Brand-safe. Key objects: pasta, pan. Best pre-roll at 12.1s."
}
```

**Without ZEROCLICK_API_KEY:** local fallback uses CPM map + hook timestamps.
CPM map: food $3.50 · unboxing $4.00 · sports $3.80 · asmr $2.50 · hack $3.20
Scales by viral score: `base_cpm × (0.7 + 0.6 × viral_score)`

```bash
curl http://localhost:8000/briefs                   # all briefs
curl http://localhost:8000/briefs/{video_id}        # single brief
```

---

## Layer 3 — GAM + The Trade Desk

### Enable/disable

```bash
ENABLE_GAM=false    # true when GAM credentials are set
ENABLE_TTD=false    # true when TTD credentials are set
```

### GAM setup

```bash
# .env
GAM_NETWORK_CODE=12345678       # GAM Dashboard → Admin → Network settings
GAM_ACCESS_TOKEN=ya29.xxx       # OAuth2 bearer token
GAM_REFRESH_TOKEN=1//xxx        # for auto-refresh on expiry
GAM_CLIENT_ID=xxx.apps.googleusercontent.com
GAM_CLIENT_SECRET=GOCSPX-xxx
GAM_ORDER_ID=existing_order_id  # GAM → Delivery → Orders
```

See `docs/AD_NETWORK_INTEGRATION.md` for full OAuth2 setup.

### TTD setup

```bash
# .env
TTD_API_KEY=your_key
TTD_ADVERTISER_ID=your_id
TTD_PARTNER_ID=your_id
# Contact: partnersupport@thetradedesk.com for access
```

### Activate a deal

```bash
# Single video — creates GAM line item + TTD PMP deal
curl -X POST "http://localhost:8000/deals/activate/{video_id}?networks=gam,ttd"

# Via campaign match (top 10 placements activated automatically)
curl -X POST http://localhost:8000/campaigns/match \
  -H "Content-Type: application/json" \
  -d '{
    "name": "HexClad Q2",
    "advertiser": "HexClad",
    "vertical": "kitchenware",
    "target_audience": "food enthusiasts 25-44",
    "budget_usd": 10000,
    "max_cpm": 4.50,
    "activate_on_networks": true,
    "networks": ["gam","ttd"]
  }'
```

### Revenue dashboard

```bash
curl http://localhost:8000/revenue
# Returns: total_revenue_usd, total_deals, total_impressions, by_platform

# Refresh deal stats from network
curl "http://localhost:8000/revenue/deals/{deal_id}/refresh?platform=ttd"

# Neo4j
docker compose exec neo4j cypher-shell -u neo4j -p viralpass123 \
  "MATCH (d:AdDeal) RETURN d.platform, sum(d.revenue_usd) as revenue, count(d) as deals"
```

### Revenue math

At 500 videos × avg 100K views × $4 CPM:
- Gross revenue: $200,000
- Platform 30% cut: **$60,000–70,000 per campaign cycle**

---

## Layer 4 — Opus 4.6 Campaign Matching

### How it works

`POST /campaigns/match` with Anthropic Opus 4.6 + extended thinking (8K tokens):
1. Reads 100 top videos from Neo4j
2. Opus reasons across full corpus — ranks placements with written reasoning
3. Returns media plan + optionally activates on GAM/TTD
4. Writes `:Campaign` + `[:TARGETS]` edges to Neo4j

### Campaign brief fields

```json
{
  "name": "Campaign name",
  "advertiser": "Brand name",
  "vertical": "kitchenware",
  "target_audience": "food enthusiasts 25-44",
  "budget_usd": 10000,
  "max_cpm": 4.50,
  "brand_safety_level": "standard",
  "preferred_categories": ["food_cooking"],
  "ad_format": "both",
  "campaign_objective": "awareness",
  "activate_on_networks": true,
  "networks": ["gam", "ttd"]
}
```

Requires: `ANTHROPIC_API_KEY`
Cost: ~$3–8 per call (Opus with extended thinking)
Margin: ~84% at $500–$2K/month SaaS pricing

---

## LTX Creative Generation

```bash
# Generate 6s bumper for a video
curl -X POST "http://localhost:8000/creatives/generate/{video_id}?ad_format=6s_bumper"

# Generate for all Opus-ranked campaign placements
curl -X POST "http://localhost:8000/creatives/campaign/{campaign_id}?ad_format=6s_bumper"

# List creatives for a video
curl http://localhost:8000/creatives/video/{video_id}
```

Ad formats: `6s_bumper` · `15s_preroll` · `thumbnail`

Without `LTX_API_KEY`: returns simulated creative URLs (full pipeline still works).

---

## MCP Manifest for AI Agent Discovery

`GET /.well-known/mcp.json` — exposes all 5 tools to AI buying agents:

```json
{
  "mcp_version": "1.0",
  "server_name": "viral-video-intelligence",
  "pricing_model": "x402_per_query_usdc",
  "chain": "ARB",
  "tools": [
    {"name": "viral_intel_search",         "price_usdc": 0.05,  "endpoint": "POST /search/semantic"},
    {"name": "viral_intel_campaign_match", "price_usdc": 0.50,  "endpoint": "POST /campaigns/match"},
    {"name": "viral_intel_trend_report",   "price_usdc": 0.25,  "endpoint": "POST /trends/detect"},
    {"name": "viral_intel_compliance_check","price_usdc": 0.05, "endpoint": "POST /compliance/check/{id}"},
    {"name": "viral_intel_top_hooks",      "price_usdc": 0.025, "endpoint": "GET /search/top-hooks"}
  ]
}
```

AI agents discover tools here, pay via Circle USDC, call endpoints autonomously.
Same architecture as MEV Shield on vectorblock.io.

---

## TrackIt Workflow + MAM

```bash
# Submit video to 8-step state machine
curl -X POST http://localhost:8000/trackit/workflow/{video_id}

# Check pipeline progress
curl http://localhost:8000/trackit/workflow/{workflow_id}/status

# Push SMPTE ST 2067 metadata to broadcaster MAM
curl -X POST http://localhost:8000/trackit/mam/{video_id}

# Audit trail (immutable log of all pipeline decisions)
curl http://localhost:8000/trackit/audit

# QoE metrics
curl http://localhost:8000/trackit/qoe/{video_id}
```

Without `TRACKIT_API_KEY`: runs locally, writes audit to `/app/downloads/audit_trail.ndjson`.

---

## Revenue activation order

```
Week 1: TWELVELABS + ANTHROPIC → pipeline + Opus, no ads
Week 2: + ZEROCLICK              → real ZeroClick briefs
Week 3: + CIRCLE + CIRCLE_WALLET → live x402 USDC micropayments
Week 4: + LTX_API_KEY            → real AI video creatives
Week 5: + ENABLE_GAM=true + all GAM keys
         + ENABLE_TTD=true + all TTD keys  → live deal activation
```
