# SERVICES.md — Backend Services Reference

## File map

| File | Class/Module | Responsibility |
|------|-------------|----------------|
| `config.py` | `Settings` | All env vars via pydantic-settings |
| `database.py` | `Neo4jDB` | All graph read/write operations |
| `ingestion.py` | `VideoIngestionService` | YouTube + TikTok discovery + download |
| `twelvelabs_service.py` | `TwelveLabsService` | Marengo search + Pegasus segment/comply |
| `zeroclick_service.py` | `ZeroClickService` | Advertiser brief generation |
| `opus_service.py` | module functions | 3 Opus 4.6 jobs |
| `adnetwork_service.py` | `GAMService`, `TTDService`, `RevenueTracker` | Ad network activation |
| `circle_x402_service.py` | `CircleWalletService`, `X402PaymentGate` | USDC payments + x402 gate |
| `ltx_service.py` | `LTXService` | AI video creative generation |
| `trackit_service.py` | `TrackItWorkflowEngine` | Pipeline orchestration + MAM |
| `worker.py` | module functions | RQ background pipeline jobs |
| `main.py` | FastAPI app | 47 endpoint handlers |

---

## config.py — Settings

Pydantic-settings reads from environment. All fields have defaults.
Import: `from config import settings, VIDEO_CATEGORIES, TIKTOK_HASHTAGS`

Key field groups:
- API keys: `twelvelabs_api_key`, `anthropic_api_key`, `zeroclick_api_key`, etc.
- GAM: `gam_access_token`, `gam_refresh_token`, `gam_client_id`, `gam_client_secret`, `gam_network_code`, `gam_order_id`
- TTD: `ttd_api_key`, `ttd_advertiser_id`, `ttd_partner_id`
- Circle: `circle_api_key`, `circle_wallet_id`, `circle_entity_secret`, `circle_environment`
- x402: `x402_price_per_query`, `x402_price_campaign_match`, `x402_price_trend_report`, `x402_enforce_payment`
- LTX: `ltx_api_key`, `ltx_default_format`
- TrackIt: `trackit_api_key`, `trackit_partner_id`, `trackit_mam_endpoint`
- Flags: `enable_gam`, `enable_ttd`
- Ingestion: `target_videos`, `min_views`, `tiktok_split`, category counts

---

## ingestion.py — VideoIngestionService

### Discovery flow

```python
# YouTube (primary)
await ingestion_service.search_youtube_shorts(query, max_results=50)
# Uses YouTube Data API v3 if YOUTUBE_API_KEY set
# Falls back to yt-dlp ytsearch if no key

# TikTok (yt-dlp, no API key needed)
await ingestion_service.search_tiktok(category_key, max_results=30)
# Scrapes tiktok.com/tag/{hashtag} with browser headers
# Rate limited to 30 per hashtag

# Combined discovery respecting TIKTOK_SPLIT
await ingestion_service.discover_videos_for_category(category_key, target_count)
```

### Viral score formula
```python
view_norm       = min(log10(max(view_count, 1)) / 7.0, 1.0)
engagement_rate = min((like_count + comment_count) / max(view_count, 1), 0.1) * 10
viral_score     = round(min((0.45 * view_norm) + (0.30 * engagement_rate) + 0.25, 1.0), 4)
```

### Download + cleanup
```python
local_path = ingestion_service.download_video(video_id, url)
# Downloads to /app/downloads/{video_id}.mp4
# MUST be deleted after TwelveLabs upload (see worker.py try/finally)
```

---

## twelvelabs_service.py — TwelveLabsService

```python
# Index from URL (preferred — no download)
tl_video_id = await tl_service.index_video_from_url(watch_url, video_id)

# Index from file (fallback)
tl_video_id = await tl_service.index_video_from_file(local_path, video_id)

# Semantic search (Marengo 2.7)
results = await tl_service.semantic_search(query, index_id, limit)

# Segmentation (Pegasus 1.2)
segments = await tl_service.segment_video(tl_video_id)
# Returns: [{segment_type, t_start, t_end, attention_score, confidence}, ...]

# Compliance (Pegasus 1.2 rules-based)
flags = await tl_service.check_compliance(tl_video_id)
# Returns: [{rule, severity, t_start, t_end, explanation}, ...]

# Advertiser context extraction
context = await tl_service.extract_advertiser_context(tl_video_id)
# Returns: {mood, key_objects, palette, audience_signals, brand_safe}
```

Polling: `_poll_task(task_id)` retries every 8s until status=ready (max 5min).
Simulation: returns mock data when `TWELVELABS_API_KEY` not set.

---

## zeroclick_service.py — ZeroClickService

```python
brief = await zeroclick_service.generate_brief(
    video_meta=video_meta,
    tl_context=tl_context,   # from extract_advertiser_context()
    segments=segments,
)
# Returns: {headline, placement_moment, target_verticals, estimated_cpm, zeroclick_context}
```

**Fallback (no API key):** `_local_brief_fallback()` uses:
- CPM map per category (food: $3.50, unboxing: $4.00, sports: $3.80, asmr: $2.50, hack: $3.20)
- Scales by viral_score: `base_cpm * (0.7 + 0.6 * viral_score)`
- placement_moment = t_start of highest-scored Hook segment

---

## opus_service.py — module functions

Three async functions, each calling Anthropic API:

```python
# 1. Ontology inference — reads corpus, extends graph schema
patch = await infer_ontology(corpus_snapshot, current_schema)
# Returns: {new_node_types, new_relationships, schema_cypher_patch, reasoning_summary}

# 2. Campaign matching — extended thinking enabled
media_plan = await match_campaign_to_inventory(
    campaign_brief=brief,
    video_inventory=videos,
    compliance_flags=flags,
)
# Returns: {placements: [{rank, video_id, timestamp, reasoning, ...}], executive_summary}

# 3. Trend detection
trends = await detect_trends(current_week_data, previous_week_data)
# Returns: {trends: [{name, velocity_score, advertiser_verticals, window_to_act}]}
```

Model: `claude-opus-4-20250514`
Extended thinking: enabled for campaign matching only (`budget_tokens: 8000`)
Requires: `ANTHROPIC_API_KEY`

---

## adnetwork_service.py

### GAMService
```python
# Check if enabled
gam_service.enabled  # False if ENABLE_GAM=false or no token

# Create line item
result = await gam_service.create_line_item(brief, video_meta, order_id)
# Returns: {status, platform, line_item_id, targeting_summary}
# Auto-refreshes OAuth token on 401 via _refresh_gam_token()

# Get stats
stats = await gam_service.get_delivery_stats(line_item_id)
```

### TTDService
```python
ttd_service.enabled  # False if ENABLE_TTD=false or no key

deal = await ttd_service.create_pmp_deal(brief, video_meta)
# Returns: {DealId, FloorCPM, TargetCPM, Targeting}

results = await ttd_service.create_campaign_from_plan(media_plan)
```

### RevenueTracker
```python
revenue_tracker.upsert_deal(deal_id, platform, data)
summary = revenue_tracker.get_revenue_summary()
```

Both services simulate when not enabled (return realistic fake data).

---

## circle_x402_service.py

### CircleWalletService
```python
circle_service.enabled  # False if no CIRCLE_API_KEY

balance = await circle_service.get_wallet_balance()
intent  = await circle_service.create_payment_intent(amount_usdc, query_type)
result  = await circle_service.verify_transfer(transfer_id, expected_amount)
# sim_ prefix always passes in demo mode

history = await circle_service.get_transaction_history(limit)
```

### X402PaymentGate
```python
# Usage at top of paid endpoint
gate_resp = await x402_gate.gate(request, "semantic_search")
if gate_resp:
    return gate_resp  # returns 402 with payment instructions

# Stats
stats = x402_gate.get_payment_stats()
```

PAYMENT_TIERS dict:
- `semantic_search`: `settings.x402_price_per_query` (default $0.05)
- `campaign_match`: `settings.x402_price_campaign_match` (default $0.50)
- `trend_detect`: `settings.x402_price_trend_report` (default $0.25)
- `brief_lookup`: `settings.x402_price_per_query * 0.5` (default $0.025)

---

## ltx_service.py — LTXService

```python
ltx_service.enabled  # False if no LTX_API_KEY

creative = await ltx_service.generate_creative(
    brief=brief,
    tl_context=tl_context,
    video_meta=video_meta,
    ad_format="6s_bumper",  # or 15s_preroll, thumbnail
)
# Returns: {creative_id, video_url, thumbnail_url, duration, ad_format, status}

creatives = await ltx_service.generate_campaign_creatives(placements, ad_format)
```

**Prompt builder:** `build_ltx_prompt(brief, tl_context, video_meta, ad_format)`
Combines: mood + key_objects + placement_moment + verticals + CTA + category → LTX prompt

Simulation: returns `{status: "simulated", video_url: "https://ltx.studio/simulated/..."}` when no key.

---

## trackit_service.py — TrackItWorkflowEngine

```python
trackit_engine.enabled  # False if no TRACKIT_API_KEY

# Submit video to workflow
result = await trackit_engine.submit_workflow(video_id, video_meta)

# Record pipeline state transition
trackit_engine.record_state_transition(workflow_id, video_id, state, data, success)
# Writes to: Neo4j (:WorkflowEvent) + /app/downloads/audit_trail.ndjson

# Push SMPTE MAM metadata
mam_result = await trackit_engine.push_to_mam(video_meta, segments, flags, brief)

# CDN registration
cdn = await trackit_engine.register_creative_cdn(creative, video_id)

# QoE metrics
qoe = trackit_engine.compute_qoe_score(video_meta)
# Returns: {qoe_score, estimated_vmaf, mobile_optimised}
```

**PIPELINE_STATES** (in order):
`video_discovered` → `tl_indexed` → `segments_extracted` → `compliance_checked` →
`brief_generated` → `creative_generated` → `deal_activated` → `payment_recorded`

**Timecode conversion:** `_seconds_to_tc(seconds, fps=25.0)` → `"HH:MM:SS:FF"`
