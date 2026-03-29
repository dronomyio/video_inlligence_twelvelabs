---
name: viral-intel-ops
version: 1.0.0
description: >
  Use this skill for ViralIntel operations — running the ingestion pipeline,
  starting/stopping Docker services, checking service health, debugging errors,
  configuring environment variables, monitoring Neo4j graph stats, and managing
  TikTok/YouTube video discovery. Activate when the user mentions: pipeline,
  Docker, start, stop, logs, debug, env, config, ingest, discover, TikTok,
  YouTube, health, status, or worker.
metadata:
  openclaw:
    requires:
      env:
        - TWELVELABS_API_KEY
        - ANTHROPIC_API_KEY
      bins:
        - docker
        - python3
        - curl
    primaryEnv: TWELVELABS_API_KEY
---

# ViralIntel — Operations Skill

## Quick start

```bash
cd viral-intel-nab2026
cp .env.example .env        # fill in API keys
./start.sh up               # start all 5 services (~3-5 min first run)
./start.sh pipeline         # ingest 500 videos (20-60 min)
./start.sh infer            # Opus 4.6 ontology inference
./start.sh test             # smoke test all 47 endpoints
```

## start.sh commands

| Command | What it does |
|---------|-------------|
| `./start.sh up` | Build + start all 5 Docker services |
| `./start.sh down` | Stop all services (keeps data) |
| `./start.sh restart` | Restart all services |
| `./start.sh logs` | Tail all logs |
| `./start.sh logs backend` | Tail one service |
| `./start.sh status` | Health + graph stats + revenue |
| `./start.sh test` | 20 API smoke tests |
| `./start.sh pipeline` | Start 500-video ingestion |
| `./start.sh infer` | Opus 4.6 ontology inference |
| `./start.sh reset` | Wipe all data, start fresh |

## Docker commands

```bash
# Service management
docker compose up -d --build        # build + start
docker compose down                 # stop (keep data)
docker compose down -v              # stop + wipe all volumes
docker compose ps                   # service status
docker stats                        # live CPU/RAM usage

# Logs
docker compose logs -f backend      # follow backend logs
docker compose logs -f worker       # follow pipeline worker
docker compose logs --tail=100      # last 100 lines all services

# Debug
docker compose exec backend bash    # shell into backend
docker compose exec backend python -c "from database import db; print(db.get_graph_stats())"
docker compose exec neo4j cypher-shell -u neo4j -p viralpass123

# Rebuild one service after code change
docker compose up -d --build backend
```

## Five Docker services

| Service | Container | Port | Role |
|---------|-----------|------|------|
| neo4j | viral_neo4j | 7474 (UI) / 7687 (Bolt) | Graph database |
| redis | viral_redis | 6379 | Job queue |
| backend | viral_backend | 8000 | FastAPI |
| worker | viral_worker | — | RQ pipeline |
| frontend | viral_frontend | 3000 | React UI |

## Service URLs

| URL | What it is |
|-----|-----------|
| http://localhost:3000 | React UI |
| http://localhost:8000 | FastAPI |
| http://localhost:8000/docs | Swagger UI |
| http://localhost:7474 | Neo4j Browser (neo4j / viralpass123) |

## Environment variables — minimum required

```bash
# REQUIRED — nothing works without these
TWELVELABS_API_KEY=your_key
ANTHROPIC_API_KEY=your_key

# RECOMMENDED — faster YouTube search
YOUTUBE_API_KEY=your_key

# OPTIONAL — each activates a revenue layer
ZEROCLICK_API_KEY=     # advertiser briefs (has local fallback)
CIRCLE_API_KEY=        # USDC micropayments
CIRCLE_WALLET_ID=      # Circle wallet
LTX_API_KEY=           # AI creative generation
TRACKIT_API_KEY=       # workflow orchestration

# AD NETWORK KILL SWITCHES (default false = simulate)
ENABLE_GAM=false
ENABLE_TTD=false
```

## Ingestion config

```bash
TARGET_VIDEOS=500       # total to ingest
MIN_VIEWS=1000          # minimum view count filter
TIKTOK_SPLIT=0.40       # 40% TikTok + 60% YouTube

# Category counts (must sum to TARGET_VIDEOS)
FOOD_COUNT=175
UNBOXING_COUNT=125
SPORTS_COUNT=100
SATISFYING_COUNT=60
TUTORIAL_COUNT=40
```

## Video discovery — how it works

**YouTube path** (primary):
- YouTube Data API v3 → 50 results per search query
- Queries per category e.g. food: `"food transformation recipe cooking"`, `"satisfying cooking recipe short"`
- Falls back to `yt-dlp ytsearch:` if no `YOUTUBE_API_KEY`

**TikTok path** (no API key needed):
- yt-dlp scrapes `tiktok.com/tag/{hashtag}` as a browser
- 7 hashtags per category e.g. food: `foodtransformation`, `cookingvideo`, `recipetiktok`
- Rate limited to 30 videos per hashtag

**Filtering:** only keeps videos with `view_count >= MIN_VIEWS`

**Viral score:** `0.45 × view_norm + 0.30 × engagement_rate + 0.25`

## Pipeline is resumable

All Neo4j writes use `MERGE` — safe to re-run `./start.sh pipeline` multiple times.
Already-indexed videos are skipped. Failed videos are retried.

## 8 pipeline states

```
video_discovered  → tl_indexed       → segments_extracted → compliance_checked
     ↓                  ↓                    ↓                      ↓
  Neo4j :Video    TwelveLabs index    Pegasus scenes          Pegasus flags
brief_generated   → creative_generated → deal_activated   → payment_recorded
     ↓                  ↓                    ↓                      ↓
  ZeroClick.ai     LTX Studio            GAM + TTD           Circle USDC
```

## Health checks

```bash
# Quick status
curl http://localhost:8000/health
curl http://localhost:8000/graph/stats

# Full status with revenue
./start.sh status

# Pipeline progress
curl http://localhost:8000/pipeline/status

# Neo4j node counts
docker compose exec neo4j cypher-shell -u neo4j -p viralpass123 \
  "MATCH (n) RETURN labels(n)[0] as label, count(n) as count ORDER BY count DESC"
```

## Common errors + fixes

| Error | Fix |
|-------|-----|
| `Cannot connect to Docker daemon` | Open Docker Desktop app, wait for whale icon to stop spinning |
| `Port already in use` | `./start.sh down` then `./start.sh up` |
| `twelvelabs==0.3.3 not found` | Remove that line from `requirements.txt` (SDK not used, direct HTTP calls only) |
| `WARN: version is obsolete` | Remove `version: '3.9'` from top of `docker-compose.yml` |
| Pipeline stalls at `tl_indexed` | TwelveLabs URL indexing failing — check `TWELVELABS_API_KEY` |
| TikTok returns 0 results | TikTok rate-limited — wait 10 min and retry, or set `TIKTOK_SPLIT=0` |
| Neo4j health check fails | Increase `--health-retries` or give Neo4j more memory in Docker settings |

## After pipeline completes — next steps

```bash
# 1. Run Opus ontology inference (discovers new node types)
./start.sh infer

# 2. Generate LTX creatives for top videos
curl -X POST "http://localhost:8000/creatives/generate/{video_id}?ad_format=6s_bumper"

# 3. Match an advertiser campaign
curl -X POST http://localhost:8000/campaigns/match \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","advertiser":"HexClad","vertical":"kitchenware","budget_usd":10000,"max_cpm":4.5,"activate_on_networks":false}'

# 4. Check revenue dashboard
curl http://localhost:8000/revenue
```

## Make targets

```bash
make up           # start services
make status       # health + stats
make test-all     # full pytest suite (inside Docker)
make neo4j-stats  # node counts
make api-revenue  # revenue dashboard
make env-check    # show which keys are set/missing
```
