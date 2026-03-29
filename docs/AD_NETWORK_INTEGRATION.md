# Ad Network Integration Guide — Path A Revenue

## Overview

Two integrations, both with graceful simulation fallback:

```
ZeroClick Brief
     │
     ├── Google Ad Manager (GAM) → line item with contextual targeting
     │         revenue share: ~30% to publisher (you)
     │
     └── The Trade Desk (TTD) → PMP deal with moment-level signals  
               revenue share: ~35% margin on media spend
```

Both services simulate responses when API keys are absent — the UI
always shows data. Activate one or both when ready.

---

## Google Ad Manager Setup (2-3 days)

### What you get
- Line items created automatically per ZeroClick brief
- Contextual keyword targeting (category, mood, objects)
- Custom key-value pairs for viral_score, placement_timestamp
- Revenue: CPM-based, Google pays ~55-70% of gross ad revenue to publisher

### Step 1: Enable GAM API access
1. Go to [Google Ad Manager](https://admanager.google.com)
2. Admin → Global settings → API access → Enable
3. Note your **Network Code** (e.g. `12345678`) → set `GAM_NETWORK_CODE`

### Step 2: OAuth2 credentials
```bash
# Install Google Ads client library
pip install google-ads

# Create OAuth2 credentials at console.cloud.google.com
# Enable: Google Ad Manager API
# Create: OAuth 2.0 Client ID (type: Web application)
# Download client_secret.json
```

```python
# Generate access token (run once, store refresh token)
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/dfp']
flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
creds = flow.run_local_server(port=0)
print(f"Access token: {creds.token}")
print(f"Refresh token: {creds.refresh_token}")
```

Set in `.env`:
```
GAM_ACCESS_TOKEN=ya29.your_access_token_here
GAM_NETWORK_CODE=12345678
GAM_ORDER_ID=existing_order_id  # or leave blank to create new
```

### Step 3: Create an Order in GAM
1. Delivery → Orders → New Order
2. Advertiser: create "ViralIntel Programmatic"
3. Note the Order ID → set `GAM_ORDER_ID`

### Step 4: Test the integration
```bash
# With containers running:
curl -X POST http://localhost:8000/deals/activate/YOUR_VIDEO_ID \
  -H "Content-Type: application/json" \
  --data-urlencode "networks=gam"

# Should return:
# {"status": "activated", "results": {"gam": {"status": "created", "line_item_id": "..."}}}
```

### What gets created in GAM
Each `POST /deals/activate/{video_id}` creates a line item with:
- Contextual keyword targeting from the video's TwelveLabs labels
- Custom key-values: `viral_score=high`, `placement_timestamp=12s`, `category=food_cooking`
- CPM floor = estimated_cpm × 0.8
- Impression goal = view_count × 0.1
- Creative format: in-stream video 640×480

---

## The Trade Desk Setup (3-5 days)

### What you get
- Private Marketplace (PMP) deals per placement moment
- Richer contextual signals than GAM (moment-level metadata)
- Access to TTD's 1B+ cookie/device graph for audience extension
- Revenue: 30-40% margin on managed spend

### Step 1: Get API access
1. Email partnersupport@thetradedesk.com — request API Partner access
2. Reference: "Programmatic video contextual targeting platform"
3. You'll receive: `TTD_API_KEY`, `TTD_ADVERTISER_ID`, `TTD_PARTNER_ID`

Timeline: 3-5 business days for approval.

Set in `.env`:
```
TTD_API_KEY=your_ttd_api_key
TTD_ADVERTISER_ID=your_advertiser_id  
TTD_PARTNER_ID=your_partner_id
```

### Step 2: Test deal creation
```bash
curl -X POST http://localhost:8000/deals/activate/YOUR_VIDEO_ID \
  --data-urlencode "networks=ttd"

# Returns deal_id like: viral-intel-a3f2b1c4d5e6
```

### Step 3: Connect deal to an ad group in TTD UI
1. TTD platform → Campaigns → New Campaign
2. Ad Groups → New Ad Group → Inventory → Private Deals
3. Enter deal_id from the API response
4. Set bid = target_cpm from the deal spec

### What gets sent to TTD
```json
{
  "DealId": "viral-intel-a3f2b1c4d5e6",
  "FloorCPM": 3.32,
  "TargetCPM": 4.15,
  "Targeting": {
    "ContentCategories": ["IAB8", "IAB26"],
    "Keywords": ["cooking", "food", "recipe", "transformation"],
    "CustomAudienceContextualSignals": {
      "ViralScore": 0.87,
      "PlacementOffset": 12.1,
      "Category": "food_cooking",
      "Verticals": ["CPG", "kitchenware"]
    }
  }
}
```

---

## Campaign-level activation (both networks simultaneously)

Use the `/campaigns/match` endpoint with `activate_on_networks: true`:

```bash
curl -X POST http://localhost:8000/campaigns/match \
  -H "Content-Type: application/json" \
  -d '{
    "name": "HexClad Q2 Cookware",
    "advertiser": "HexClad",
    "vertical": "kitchenware",
    "target_audience": "food enthusiasts 25-44",
    "budget_usd": 10000,
    "max_cpm": 4.50,
    "brand_safety_level": "standard",
    "preferred_categories": ["food_cooking"],
    "campaign_objective": "awareness",
    "activate_on_networks": true,
    "networks": ["gam", "ttd"]
  }'
```

This calls Opus 4.6 to rank your inventory → creates TTD PMP deals for
top 10 placements → creates GAM line items for top 5 → writes all deal
IDs back to Neo4j → returns the full media plan with network activation status.

---

## Revenue tracking

All deals write to the `(:AdDeal)` Neo4j node and the revenue dashboard:

```bash
# Full revenue summary
curl http://localhost:8000/revenue

# Refresh a specific deal's impression/spend stats
curl http://localhost:8000/revenue/deals/DEAL_ID/refresh?platform=ttd

# All active deals
curl http://localhost:8000/deals
```

Neo4j graph:
```cypher
MATCH (v:Video)-[:HAS_DEAL]->(d:AdDeal)
RETURN v.title, d.platform, d.impressions, d.revenue_usd
ORDER BY d.revenue_usd DESC
```

---

## Revenue split model

| Party | GAM share | TTD share | Notes |
|-------|-----------|-----------|-------|
| Your platform | 30% | 35% | Intelligence layer margin |
| Publisher/creator | 55% | 50% | YouTube/TikTok rev-share pass-through |
| Google/TTD | 15% | 15% | Platform fee |

At 500 videos × avg 100K views × $4 CPM:
- Gross revenue: $200,000
- Your 30-35% cut: **$60,000–$70,000**

At 5,000 videos (scale): **$600K–$700K per campaign cycle**

---

## Simulation mode (no API keys needed)

When `GAM_ACCESS_TOKEN` or `TTD_API_KEY` are not set, both services
return realistic simulated responses with randomised impression and
revenue data. The UI, Neo4j graph, and revenue dashboard all work
identically — you can demo the full flow without live credentials.

Simulated deal IDs are prefixed `gam_sim_` and `ttd_sim_` so you can
distinguish them in the graph.
