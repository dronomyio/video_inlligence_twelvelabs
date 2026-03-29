# ARCHITECTURE.md — System Design & Data Flow

## High-level architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  React Frontend (:3000) — 10 pages                               │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST / JSON
┌──────────────────────────▼──────────────────────────────────────┐
│  FastAPI Backend (:8000) — 47 endpoints                          │
│  main.py · config.py · database.py                               │
└──┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬────────────┘
   │      │      │      │      │      │      │      │
  TL    Neo4j  ZC    Opus   Circle  LTX  TrackIt  GAM/TTD
   │      │      │      │      │      │      │      │
Marengo :7687  .ai   4.6   Arc   Studio  MAM  Demand
Pegasus        API   ext   ARB   API   CDN   platforms
   │      │      │      │             │
   └──────┴──────┘      │             │
     worker.py          │             │
     (RQ + Redis)       └─────────────┘
     8-step pipeline       revenue stack
```

## Five Docker services

| Service | Container | Port | Role |
|---------|-----------|------|------|
| neo4j | viral_neo4j | 7474 (UI), 7687 (Bolt) | Graph database |
| redis | viral_redis | 6379 | Job queue |
| backend | viral_backend | 8000 | FastAPI API server |
| worker | viral_worker | — | RQ pipeline jobs |
| frontend | viral_frontend | 3000 | React UI |

Start order: neo4j + redis → backend → worker → frontend

## Request lifecycle — a paid API call

```
Client
  │
  ▼
POST /search/semantic
  │
  ├─► X402PaymentGate.gate(request, "semantic_search")
  │       └─► if ENFORCE=true: check X-Payment-Transfer-Id header
  │               └─► CircleWalletService.verify_transfer()
  │                       └─► Circle Arc API (or sim_ prefix passes)
  │
  ├─► TwelveLabsService.semantic_search(query)
  │       └─► TwelveLabs Marengo 2.7 REST API
  │
  ├─► Neo4jDB.search_by_semantic_label(label)
  │       └─► Neo4j Bolt :7687
  │
  └─► return {results, query, track: "search"}
```

## Data flow — full ingestion pipeline

```
discover_videos_for_category()
    │
    ├─ YouTube: YouTube Data API v3 → search results
    │           (fallback: yt-dlp ytsearch)
    │
    └─ TikTok:  yt-dlp tiktok.com/tag/{hashtag}
                (no API key, public scraping)
         │
         ▼
    VideoIngestionService.compute_viral_score()
    viral_score = 0.45×view_norm + 0.30×engagement_rate + 0.25
         │
         ▼
    TwelveLabsService.index_video_from_url()
    (fallback: download → index_video_from_file → delete MP4)
         │
         ▼
    TwelveLabsService.segment_video()         [Pegasus 1.2]
    → Hook / Build / Payoff / CTA segments
    → viral_seg_score = 0.60×attention + 0.40×confidence
         │
         ▼
    TwelveLabsService.check_compliance()      [Pegasus 1.2]
    → alcohol / violence / brand_safety / child_safety flags
         │
         ▼
    ZeroClickService.generate_brief()
    → placement_moment, estimated_cpm, target_verticals
    (fallback: local CPM map + hook segment scoring)
         │
         ▼
    Neo4jDB.upsert_video() + upsert_scene() + upsert_advert_brief()
    TrackItWorkflowEngine.record_state_transition()
```

## Opus 4.6 jobs

Three async jobs, each reading across the full corpus:

| Job | Endpoint | Input | Output |
|-----|----------|-------|--------|
| Ontology inference | POST /ontology/infer | 500 scene labels + Neo4j schema | Cypher DDL patch for new node types |
| Campaign matching | POST /campaigns/match | Campaign brief + 100 videos | Ranked media plan + per-placement reasoning |
| Trend detection | POST /trends/detect | Corpus snapshot + previous week | Velocity-scored emerging patterns |

Campaign matching uses `thinking: {type: "enabled", budget_tokens: 8000}`.

## Revenue stack

```
x402 USDC micropayments (Circle Arc/Arbitrum)
    $0.05 search · $0.50 campaign · $0.25 trend
         +
ZeroClick.ai advertiser briefs
    machine-readable placement cards
         +
GAM line items (contextual key-value targeting)
TTD PMP deals (moment-level signals)
    30–35% platform margin · $3–6 CPM
         +
Opus 4.6 campaign matching (SaaS)
    $500–$2,000/month/seat
```

## Key design decisions

**Why Neo4j over Postgres?**
Cross-corpus queries: "find all Hook segments featuring cookware in videos
where creator has >1M subscribers and no compliance flags" require graph
traversal. Neo4j handles this in one Cypher query; Postgres would need
5+ JOINs across normalised tables.

**Why x402 not API keys?**
AI buying agents can pay per query autonomously. No account setup, no
monthly subscription friction. Same architecture as MEV Shield on
vectorblock.io.

**Why yt-dlp for TikTok?**
TikTok Research API requires approved application (2–4 weeks). yt-dlp
scrapes public hashtag pages as a browser would — no approval needed,
works immediately. 30-video/hashtag rate limit to avoid blocks.

**Why delete MP4 after indexing?**
TwelveLabs holds embeddings in the cloud. Local file is only needed for
the upload. At 500 videos × ~10 MB = ~5 GB would otherwise accumulate.
`try/finally` in worker.py ensures cleanup even on upload failure.
