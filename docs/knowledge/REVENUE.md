# REVENUE.md — Monetisation Layers

## Four stacked revenue layers

```
Layer 1: x402 USDC micropayments    ← per-query, Circle Arc/Arbitrum
Layer 2: ZeroClick.ai briefs        ← machine-readable placement cards
Layer 3: GAM + TTD deal activation  ← 30–35% platform margin
Layer 4: Opus SaaS subscription     ← $500–$2K/month/seat
```

---

## Layer 1 — x402 USDC Micropayments

### How it works

Every paid API query goes through `X402PaymentGate.gate()` in `circle_x402_service.py`:

```
Client request arrives
    ↓
Check X-Payment-Transfer-Id header
    ├── Missing + enforcement ON → return HTTP 402 with deposit address
    └── Present → CircleWalletService.verify_transfer(transfer_id, amount)
                      ├── Verified → allow request, record (:Payment) node
                      └── Not verified → return HTTP 402
```

### Pricing

| Query type | Price | Endpoint |
|-----------|-------|---------|
| Semantic search | $0.05 USDC | POST /search/semantic |
| Campaign match | $0.50 USDC | POST /campaigns/match |
| Trend report | $0.25 USDC | POST /trends/detect |
| Brief lookup | $0.025 USDC | GET /briefs/{id} |

### Demo mode

`X402_ENFORCE_PAYMENT=false` (default) → gate always passes, no payment needed.
`sim_*` transfer IDs always verify even when enforcement is on.

### AI agent flow

1. Agent reads `GET /.well-known/mcp.json` → discovers tools + prices
2. Agent calls `POST /circle/payment-intent?query_type=semantic_search`
3. Gets deposit address + amount
4. Sends USDC to address on Arbitrum
5. Retries original request with `X-Payment-Transfer-Id: {transfer_id}`
6. Gate verifies → request served

### Revenue tracking

All payments stored as `(:Payment)` nodes in Neo4j.
`GET /x402/stats` returns revenue by query type.

---

## Layer 2 — ZeroClick.ai Advertiser Briefs

Each indexed video gets a machine-readable placement card:
```json
{
  "headline": "...",
  "placement_moment": 12.1,
  "target_verticals": ["CPG", "kitchenware"],
  "estimated_cpm": 4.15,
  "zeroclick_context": "Brand-safe. Key objects: pasta, pan. Best pre-roll at 12.1s..."
}
```

These cards are consumed by:
- GAM targeting (`brief_to_gam_targeting()`)
- TTD deal spec (`brief_to_ttd_deal()`)
- LTX prompt builder (`build_ltx_prompt()`)
- Opus campaign matching (ranked inventory feed)

**Without ZeroClick API key:** local fallback generates equivalent briefs.

---

## Layer 3 — GAM + The Trade Desk

### GAM (Google Ad Manager)

`brief_to_gam_targeting(brief, video_meta)` produces:
```python
{
    "targeting": ["food", "cooking", "cookware", "recipe"],  # from TwelveLabs labels
    "custom_targeting": {
        "viral_score": "high",          # > 0.8
        "placement_timestamp": "12s",
        "category": "food_cooking",
    },
    "iab_categories": ["IAB8", "IAB26"],   # from VERTICAL_TO_IAB map
    "estimated_cpm_micros": 4150000,       # brief CPM × 1M
}
```

Creates a line item per placement in an existing GAM Order.
Revenue: ~55–70% of gross ad revenue flows to publisher.
Platform margin: ~30% of gross.

### The Trade Desk

`brief_to_ttd_deal(brief, video_meta)` produces:
```python
{
    "DealId": "viral-intel-a3f2b1c4",
    "FloorCPM": 3.32,            # brief_cpm × 0.8
    "TargetCPM": 4.15,           # brief_cpm
    "Targeting": {
        "ContentCategories": ["IAB8"],
        "Keywords": ["cooking", "food"],
        "CustomAudienceContextualSignals": {
            "ViralScore": 0.87,
            "PlacementOffset": 12.1,
            "Category": "food_cooking",
        }
    }
}
```

Revenue: 30–40% margin on managed spend.

### Revenue calculation example

At 500 videos × avg 100K views × $4 CPM:
- Gross revenue: $200,000
- Platform 30% cut: **$60,000–70,000**
- At 5,000 videos: **$600K–700K per campaign cycle**

### Kill switches

```bash
ENABLE_GAM=false   # prevents any GAM API calls
ENABLE_TTD=false   # prevents any TTD API calls
```

Both simulate realistic responses when disabled.

---

## Layer 4 — Opus Campaign Matching (SaaS)

`POST /campaigns/match` with `activate_on_networks: true`:

1. Reads 100 top videos from Neo4j
2. Sends to Opus 4.6 with extended thinking (8K budget)
3. Opus ranks placements with written reasoning per placement
4. Returns media plan + activates on GAM/TTD
5. Writes `:Campaign` + `[:TARGETS]` edges to Neo4j

**Pricing:** $500–$2,000/month/advertiser seat
**Opus API cost:** ~$3–8 per campaign match call
**Margin:** ~84%

**Trend intelligence add-on:**
`POST /trends/detect` → weekly Opus report for agencies
Pricing: $500–$2,000/month

---

## Revenue dashboard

```bash
curl http://localhost:8000/revenue
```

Returns:
```json
{
  "total_revenue_usd": 1247.50,
  "total_deals": 28,
  "total_impressions": 2800000,
  "by_platform": {
    "google_ad_manager": {"revenue": 820.00, "deals": 15},
    "the_trade_desk":    {"revenue": 427.50, "deals": 13}
  }
}
```

Neo4j query for full breakdown:
```cypher
MATCH (d:AdDeal)
RETURN d.platform, sum(d.revenue_usd) as revenue, count(d) as deals
ORDER BY revenue DESC
```

---

## MCP manifest for AI agent discovery

`GET /.well-known/mcp.json` returns all 5 tools with prices:

```json
{
  "tools": [
    {"name": "viral_intel_search",        "price_usdc": 0.05},
    {"name": "viral_intel_campaign_match","price_usdc": 0.50},
    {"name": "viral_intel_trend_report",  "price_usdc": 0.25},
    {"name": "viral_intel_compliance_check","price_usdc": 0.05},
    {"name": "viral_intel_top_hooks",     "price_usdc": 0.025}
  ]
}
```

AI buying agents (Claude agents, GPT agents, TTD algorithmic buyers) discover
and pay for these tools autonomously using the x402 protocol.
