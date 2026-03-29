# PIPELINE.md — Ingestion Pipeline

## Starting the pipeline

```bash
# Via start.sh (recommended)
./start.sh pipeline

# Or direct API call
curl -X POST http://localhost:8000/pipeline/start

# Check status
curl http://localhost:8000/pipeline/status

# Watch worker logs
./start.sh logs worker
```

## The 8 pipeline states

Each video passes through these states in order:

### 1. `video_discovered`
**File:** `worker.py` → `run_full_ingestion()`
**What happens:**
- `discover_videos_for_category()` searches YouTube + TikTok
- Filters by `MIN_VIEWS` (default 1,000)
- Computes `viral_score = 0.45×view_norm + 0.30×engagement_rate + 0.25`
- Calls `db.upsert_video()` → creates `:Video` node

**YouTube path:** YouTube Data API v3 → 50 results per query
**TikTok path:** yt-dlp scraping `tiktok.com/tag/{hashtag}` → 30 per hashtag
**Fallback:** yt-dlp `ytsearch:` if no YOUTUBE_API_KEY

---

### 2. `tl_indexed`
**File:** `worker.py` → `_process_single_video_async()`
**What happens:**
- Tries `tl_service.index_video_from_url(watch_url)` first
- If fails: downloads MP4 → `tl_service.index_video_from_file(path)` → **deletes MP4**
- Stores `twelvelabs_video_id` on `:Video` node

**Storage note:** MP4 deleted in `try/finally` after upload. Peak disk = ~100 MB.

---

### 3. `segments_extracted`
**File:** `worker.py`
**What happens:**
- `tl_service.segment_video(tl_video_id)` → Pegasus 1.2
- Creates `:Scene` nodes for each segment
- `viral_seg_score = 0.60×attention_score + 0.40×confidence`
- Updates `hook_strength` on `:Video` = max hook segment score
- Typical output: 4–8 segments per video

**Segment types:** `hook`, `build`, `payoff`, `cta`

---

### 4. `compliance_checked`
**File:** `worker.py`
**What happens:**
- `tl_service.check_compliance(tl_video_id)` → Pegasus rules-based
- Creates `:ComplianceFlag` nodes
- Links flags to scenes via `[:HAS_FLAG]`

**Rules checked:** `alcohol` (medium), `violence` (high), `brand_safety` (high), `child_safety` (critical)

---

### 5. `brief_generated`
**File:** `worker.py`
**What happens:**
- `tl_service.extract_advertiser_context(tl_video_id)` → mood, objects, palette
- `zeroclick_service.generate_brief(video_meta, tl_context, segments)`
  - If ZEROCLICK_API_KEY: calls ZeroClick.ai API
  - If no key: `_local_brief_fallback()` uses CPM map + hook timestamps
- `db.upsert_advert_brief(video_id, brief)` → `:AdvertBrief` node

---

### 6. `creative_generated`
**File:** `main.py` `/creatives/generate/{video_id}` (called manually or via campaign)
**What happens:**
- `build_ltx_prompt(brief, tl_context, video_meta, format)`
- `ltx_service.generate_creative(brief, tl_context, video_meta)`
  - If LTX_API_KEY: calls LTX Studio API, polls until ready
  - If no key: returns simulated creative URL
- Creates `:Creative` node, links `[:HAS_CREATIVE]` to `:Video`
- `trackit_engine.register_creative_cdn(creative, video_id)`

---

### 7. `deal_activated`
**File:** `main.py` `/deals/activate/{video_id}` or via `/campaigns/match`
**What happens:**
- Reads `:AdvertBrief` for the video
- `brief_to_gam_targeting(brief, video_meta)` → contextual keyword targeting
- `gam_service.create_line_item(...)` → GAM line item (if ENABLE_GAM=true)
- `brief_to_ttd_deal(brief, video_meta)` → PMP deal spec
- `ttd_service.create_pmp_deal(...)` → TTD deal (if ENABLE_TTD=true)
- `revenue_tracker.upsert_deal(...)` → `:AdDeal` node

---

### 8. `payment_recorded`
**File:** `circle_x402_service.py` → `X402PaymentGate._record_payment()`
**What happens:**
- Called automatically when a paid endpoint verifies payment
- Creates `:Payment` node with `transfer_id`, `amount_usdc`, `query_type`
- Also written to Neo4j by `x402_gate._record_payment()`

---

## Pipeline is resumable

Each step uses `MERGE` not `CREATE` in Neo4j. Running the pipeline again:
- Skips already-indexed videos (video_id already in graph)
- Re-runs failed steps for videos that didn't complete
- Safe to run multiple times

---

## Worker architecture

```
RQ Queue (Redis)
    │
    ├── "pipeline" queue → run_full_ingestion()
    │       │
    │       └── per-category: discover_videos_for_category()
    │               │
    │               └── per-video: process_single_video() [enqueued to "ingest" queue]
    │
    └── "ingest" queue → process_single_video()
            │
            └── _process_single_video_async() [asyncio.run()]
                    Steps 2–5 in order
```

`worker.py` runs as a separate Docker container (`viral_worker`) using `rq.Worker`.

---

## Monitoring pipeline progress

```bash
# Via start.sh
./start.sh status

# Direct API
curl http://localhost:8000/pipeline/status
# Returns: {queue_depth, ingest_queue_depth, graph_stats}

curl http://localhost:8000/graph/stats
# Returns node counts per type

# Neo4j Browser
# MATCH (v:Video) RETURN count(v) as total
# MATCH (ab:AdvertBrief) RETURN count(ab) as with_briefs
```

---

## After pipeline: run Opus inference

```bash
./start.sh infer
# Or: curl -X POST http://localhost:8000/ontology/infer
```

Opus reads all 500 scene labels and proposes new node types like `:ViralFormat`.
Run once after initial ingestion, then weekly as new content is added.
