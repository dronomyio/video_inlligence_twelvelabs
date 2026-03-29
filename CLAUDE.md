# CLAUDE.md — Viral Video Intelligence · NAB 2026

This is the root context file for Claude Code. Read this first, then load
the specific knowledge file for the task you're working on.

## What this project is

A dockerised media intelligence platform that:
1. Ingests 500 viral short-form videos (YouTube Shorts + TikTok via yt-dlp)
2. Indexes them with TwelveLabs Marengo 2.7 + Pegasus 1.2
3. Builds a Neo4j knowledge graph (13 node types, 13 relationships)
4. Runs 3 NAB hackathon tracks: Search, Segmentation, Compliance
5. Generates ZeroClick.ai advertiser placement briefs
6. Matches advertiser campaigns with Anthropic Opus 4.6 (extended thinking)
7. Generates matched video ad creatives with LTX Studio
8. Activates deals on Google Ad Manager + The Trade Desk
9. Monetises every API query with Circle USDC micropayments via x402 protocol
10. Orchestrates everything with TrackIt workflow engine + SMPTE MAM output

## Tech stack

| Layer | Technology |
|-------|-----------|
| Video AI | TwelveLabs Marengo 2.7 + Pegasus 1.2 |
| Graph DB | Neo4j 5.15 + APOC + GDS |
| AI reasoning | Anthropic Claude Opus 4.6 (extended thinking) |
| Advertiser context | ZeroClick.ai |
| Creative generation | LTX Studio API |
| Workflow + MAM | TrackIt |
| Payments | Circle Arc testnet · Arbitrum USDC · x402 |
| Ad networks | Google Ad Manager + The Trade Desk |
| Ingestion | yt-dlp + YouTube Data API v3 |
| Backend | FastAPI + RQ workers + Redis |
| Frontend | React 18 + Recharts + Framer Motion |
| Container | Docker Compose (5 services) |

## Repository structure

```
viral-intel-nab2026/
├── CLAUDE.md                     ← YOU ARE HERE
├── docs/knowledge/               ← Claude Code knowledge base
│   ├── ARCHITECTURE.md           ← system design + data flow
│   ├── API.md                    ← all 47 endpoints
│   ├── DATABASE.md               ← Neo4j schema + Cypher patterns
│   ├── SERVICES.md               ← each backend service explained
│   ├── FRONTEND.md               ← React pages + components
│   ├── ENV.md                    ← every env var + where to get it
│   ├── PIPELINE.md               ← 8-step ingestion pipeline
│   └── REVENUE.md                ← monetisation layers
├── backend/                      ← 14 Python files, 47 endpoints
├── frontend/                     ← React 18, 10 pages
├── neo4j/init/                   ← seed.cypher + init.sh
├── tests/                        ← 65 integration tests
└── docs/                         ← integration guides
```

## Key numbers

- **47** REST API endpoints
- **14** backend Python files, ~5,000 lines
- **10** React frontend pages
- **13** Neo4j node types, **13** relationships
- **65** integration tests across 13 test classes
- **500** target videos (300 YouTube + 200 TikTok at default 40% split)
- **8** pipeline states per video
- **40** environment variables

## Quick commands

```bash
./start.sh up          # start all 5 Docker services
./start.sh pipeline    # ingest 500 videos
./start.sh infer       # Opus 4.6 ontology inference
./start.sh test        # smoke test all 47 endpoints
./start.sh status      # health + graph stats + revenue
./start.sh down        # stop all services
```

## Which knowledge file to load

| Task | Load this file |
|------|---------------|
| Adding/changing API endpoints | `docs/knowledge/API.md` |
| Neo4j queries, schema changes | `docs/knowledge/DATABASE.md` |
| Backend service logic | `docs/knowledge/SERVICES.md` |
| Frontend pages, UI components | `docs/knowledge/FRONTEND.md` |
| Environment variables, config | `docs/knowledge/ENV.md` |
| Pipeline, worker, ingestion | `docs/knowledge/PIPELINE.md` |
| Revenue, payments, x402 | `docs/knowledge/REVENUE.md` |
| System design questions | `docs/knowledge/ARCHITECTURE.md` |

## Critical rules when editing this codebase

1. **All backend services gracefully fall back** when their API key is absent.
   Never remove fallback/simulation logic.
2. **x402 gate** must be called at the top of all three paid endpoints:
   `/search/semantic`, `/campaigns/match`, `/trends/detect`.
3. **Neo4j writes** use `MERGE` not `CREATE` — always idempotent.
4. **Worker cleanup** — always delete downloaded MP4 after TwelveLabs
   indexes it. The `try/finally` block in `worker.py` must stay.
5. **ENABLE_GAM / ENABLE_TTD flags** — check `settings.enable_gam` and
   `settings.enable_ttd` before any GAM/TTD API call.
6. **TikTok scraping** uses yt-dlp with browser-mimicking headers.
   Rate-limit to 30 videos per hashtag per run.
