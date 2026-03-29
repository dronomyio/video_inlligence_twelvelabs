# ENV.md — Environment Variables

All vars go in `.env` at project root.
Default values listed — leave blank to use fallback/simulation.

## Quick start minimum

```bash
TWELVELABS_API_KEY=your_key    # required — video indexing
ANTHROPIC_API_KEY=your_key     # required — Opus 4.6
```

Everything else simulates. Add keys progressively to activate each revenue layer.

---

## Core AI Services

| Variable | Required | Default | Where to get |
|----------|----------|---------|-------------|
| `TWELVELABS_API_KEY` | ✅ YES | — | platform.twelvelabs.io → API Keys |
| `ANTHROPIC_API_KEY` | ✅ YES | — | console.anthropic.com → API Keys |
| `ZEROCLICK_API_KEY` | ⚡ No | — | zeroclick.ai → Dashboard → API |
| `YOUTUBE_API_KEY` | ⚡ No | — | console.cloud.google.com → YouTube Data API v3 → Credentials |

Without `ZEROCLICK_API_KEY`: briefs generated locally using CPM map + viral score. All downstream features still work.
Without `YOUTUBE_API_KEY`: falls back to yt-dlp search (slower but finds same videos).

---

## Google Ad Manager

| Variable | Default | Notes |
|----------|---------|-------|
| `ENABLE_GAM` | `false` | Set `true` only when all GAM keys filled in |
| `GAM_NETWORK_CODE` | — | Your GAM network code (e.g. `12345678`) |
| `GAM_ACCESS_TOKEN` | — | OAuth2 bearer token |
| `GAM_REFRESH_TOKEN` | — | For auto-refresh on expiry |
| `GAM_CLIENT_ID` | — | From Google Cloud Console |
| `GAM_CLIENT_SECRET` | — | From Google Cloud Console |
| `GAM_ORDER_ID` | — | Existing GAM order to add line items to |

When `ENABLE_GAM=false`: `GAMService.enabled = False`, all calls return simulated responses.
See `docs/AD_NETWORK_INTEGRATION.md` for OAuth setup steps.

---

## The Trade Desk

| Variable | Default | Notes |
|----------|---------|-------|
| `ENABLE_TTD` | `false` | Set `true` only when TTD keys filled in |
| `TTD_API_KEY` | — | From TTD partner API access |
| `TTD_ADVERTISER_ID` | — | Your advertiser ID |
| `TTD_PARTNER_ID` | — | Your partner ID |

When `ENABLE_TTD=false`: `TTDService.enabled = False`, all calls return simulated deal IDs.
Contact: partnersupport@thetradedesk.com for API access.

---

## Circle / USDC

| Variable | Default | Notes |
|----------|---------|-------|
| `CIRCLE_API_KEY` | — | console.circle.com → API Keys |
| `CIRCLE_WALLET_ID` | — | console.circle.com → Wallets → Create |
| `CIRCLE_ENTITY_SECRET` | — | Shown once at wallet creation |
| `CIRCLE_ENVIRONMENT` | `testnet` | `testnet` = Arc sandbox, `mainnet` = real USDC |

Without these: `CircleWalletService.enabled = False`, returns `sim_*` responses.

---

## x402 Micropayment Pricing

| Variable | Default | Description |
|----------|---------|-------------|
| `X402_PRICE_PER_QUERY` | `0.05` | Semantic search, compliance check, top hooks |
| `X402_PRICE_CAMPAIGN_MATCH` | `0.50` | Opus campaign matching + ontology infer |
| `X402_PRICE_TREND_REPORT` | `0.25` | Opus trend detection |
| `X402_ENFORCE_PAYMENT` | `false` | `false` = demo mode, everyone gets in free |

When `false`: x402 gate always passes — good for demos and development.
When `true`: requires valid `X-Payment-Transfer-Id` header on paid endpoints.
`sim_*` transfer IDs always pass even when enforcement is on (testnet demo mode).

---

## LTX Studio

| Variable | Default | Notes |
|----------|---------|-------|
| `LTX_API_KEY` | — | ltx.studio → API access |
| `LTX_DEFAULT_FORMAT` | `6s_bumper` | `6s_bumper` / `15s_preroll` / `thumbnail` |

Without `LTX_API_KEY`: `LTXService.enabled = False`, returns simulated creative URLs.

---

## TrackIt

| Variable | Default | Notes |
|----------|---------|-------|
| `TRACKIT_API_KEY` | — | trackit.io → partner API |
| `TRACKIT_PARTNER_ID` | — | Your partner ID |
| `TRACKIT_MAM_ENDPOINT` | — | Broadcaster MAM webhook URL |

Without these: runs locally. Workflow state machine works, audit trail writes to
`/app/downloads/audit_trail.ndjson`, MAM metadata writes to
`/app/downloads/mam_{video_id}.json`.

---

## Infrastructure (Docker-managed)

| Variable | Default | Notes |
|----------|---------|-------|
| `NEO4J_URI` | `bolt://neo4j:7687` | Docker service name |
| `NEO4J_USER` | `neo4j` | Default Neo4j user |
| `NEO4J_PASSWORD` | `viralpass123` | Set in docker-compose.yml |
| `REDIS_URL` | `redis://redis:6379` | Docker service name |

Do not change these unless running outside Docker.

---

## Ingestion Config

| Variable | Default | Description |
|----------|---------|-------------|
| `MIN_VIEWS` | `1000` | Minimum view count to include a video |
| `TARGET_VIDEOS` | `500` | Total videos to ingest |
| `FOOD_COUNT` | `175` | food_cooking target |
| `UNBOXING_COUNT` | `125` | product_unboxing target |
| `SPORTS_COUNT` | `100` | sports_highlights target |
| `SATISFYING_COUNT` | `60` | satisfying_asmr target |
| `TUTORIAL_COUNT` | `40` | life_hack_tutorial target |
| `TIKTOK_SPLIT` | `0.40` | Fraction from TikTok (0.0–1.0) |

Note: category counts must sum to `TARGET_VIDEOS`.
At `TIKTOK_SPLIT=0.40` with 500 videos: 200 TikTok + 300 YouTube.

---

## Activation order (progressive)

Start with just two keys and add more as you get access:

```
Week 1: TWELVELABS_API_KEY + ANTHROPIC_API_KEY
        → Full pipeline, local briefs, Opus matching, no ads, no payments

Week 2: + YOUTUBE_API_KEY + ZEROCLICK_API_KEY
        → Real ZeroClick briefs, faster YouTube search

Week 3: + CIRCLE_API_KEY + CIRCLE_WALLET_ID
        → Live x402 USDC micropayments on Arc testnet

Week 4: + LTX_API_KEY
        → Real AI video creative generation

Week 5: + ENABLE_GAM=true + all GAM keys
         + ENABLE_TTD=true + all TTD keys
        → Live ad deal activation + real revenue
```
