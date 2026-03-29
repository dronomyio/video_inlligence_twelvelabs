# ViralIntel — Viral Video Intelligence Platform
### NAB 2026 Hackathon · TwelveLabs × AWS Bedrock × Anthropic × Neo4j

> **Live Demo**: https://video-intel-morphvm-54lyty6g.http.cloud.morph.so

A dockerized media intelligence stack that ingests broadcast archives and viral short-form video, enabling semantic moment retrieval, ad-break segmentation, and explainable compliance review — powered by TwelveLabs Marengo 2.7 + Pegasus 1.2, Neo4j knowledge graph, and Anthropic Claude Opus 4.6.

---

## 🎯 Hackathon Tracks

### Track 1 — Archive Search
Natural language semantic search across broadcast archives using TwelveLabs Marengo retrieval.
- Query: *"news anchor delivering breaking news urgently"* → timestamped clips in **< 1s**
- Query: *"slow motion athlete in peak performance"* → finds exact moments in Wilt Chamberlain 59-min video
- **x402 USDC micropayment gating** at $0.05/query via Circle Arc testnet

### Track 2 — Segmentation
Semantic boundary detection identifying story segments and optimal ad-break insertion points.
- Visual timeline with color-coded segment types
- Cross-corpus ad-break intelligence across all analyzed videos
- Export to JSON / XML / EDL / CSV for broadcast playout systems

### Track 3 — Compliance Guardian
Explainable compliance review powered by Anthropic Claude Opus 4.6.
- Predefined rulesets: broadcast_standards, brand_guidelines, platform_policies
- Per-violation timestamps, severity scoring, remediation suggestions
- Custom rule creation via API with human review workflow

---

## 📊 Platform Stats

| Metric | Value |
|--------|-------|
| Total Videos in Knowledge Graph | 307 |
| Long-form Archive Videos (TwelveLabs indexed) | **8** |
| Viral Short-form Videos (metadata + trend analysis) | **299** |
| Total Indexed Duration | **8 hr 49 min** |
| Trend Tags | 1,278 |
| Scene Segments | 41 |
| REST Endpoints | 47 |
| Creators | 203 |

### The 8 Long-Form Archive Videos (TwelveLabs Indexed)
| Video | Category | Duration |
|-------|----------|----------|
| ABC World News Tonight — Jan 23, 2026 | News Broadcast | ~20 min |
| NBC Nightly News Full Episode — Mar 21 | News Broadcast | ~21 min |
| NBC Nightly News Full Episode — March 7 | News Broadcast | ~20 min |
| 4K Forest — Cinematic Forest Ultra HD | Production B-Roll | ~2 min |
| A THUNDERBIRDS REUNION — Behind the Scenes | Production B-Roll | ~37 min |
| Bald Eagles on the Nooksack River — 4K | Production B-Roll | ~2 min |
| What 14 Movies Looked Like Behind the Scenes | Production B-Roll | ~13 min |
| Wilt Chamberlain Scouting Video | Sports Archive | **59 min** |

The remaining 299 videos are viral short-form content (entertainment, sports highlights, documentary) ingested as metadata with viral scores, view counts, and trend tags — demonstrating the platform's ability to handle both long-form broadcast archives and short-form social video at scale.

---

## 🏗 Architecture
```
┌──────────────────────────────────────────────────────────────┐
│                   VIDEO INGESTION LAYER                       │
│  Local Files (.mp4) ──► TwelveLabs Marengo 2.7 + Pegasus 1.2│
│  YouTube Shorts    ──► Metadata Pipeline (viral score/trends)│
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                   AI INTELLIGENCE LAYER                       │
│  TwelveLabs Marengo ──► Semantic Visual+Audio Search         │
│  TwelveLabs Pegasus ──► Chapter/Segment Extraction           │
│  Anthropic Opus 4.6 ──► Explainable Compliance Reasoning     │
│  ZeroClick.ai       ──► Advertiser Brief Generation          │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                   KNOWLEDGE GRAPH (Neo4j)                     │
│  Video ──► Scene ──► Trend ──► Creator ──► AdvertBrief       │
│  307 videos · 41 scenes · 1,278 trends · 203 creators        │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                   API LAYER (FastAPI, 47 endpoints)           │
│  /search  /segment  /compliance  /videos  /graph  /payments  │
│  x402 Micropayments ──► Circle USDC (Arc testnet) $0.05/query│
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                   FRONTEND (React 18 + Vite)                  │
│  Dashboard · Video Graph · Search · Segmentation              │
│  Compliance · Ad Briefs · Campaigns · LTX Creatives           │
│  TrackIt · Payments (x402 USDC)                               │
└──────────────────────────────────────────────────────────────┘
     Infrastructure: Docker Compose on Morph Cloud
     Services: neo4j · redis · backend · worker · frontend
```

---

## 🔧 Tech Stack

| Layer | Technology |
|-------|-----------|
| Video Understanding | TwelveLabs Marengo 2.7 + Pegasus 1.2 |
| AI Reasoning | Anthropic Claude Opus 4.6 |
| Knowledge Graph | Neo4j |
| Ad Intelligence | ZeroClick.ai |
| Payments | Circle USDC x402 (Arc testnet) |
| Video Generation | LTX Studio |
| Analytics | TrackIt |
| Backend | FastAPI (Python 3.11) |
| Frontend | React 18 + Vite + Framer Motion |
| Queue | Redis + Celery |
| Infrastructure | Docker Compose, Morph Cloud |

---

## 🚀 Quick Start
```bash
git clone https://github.com/dronomyio/video_inlligence_twelvelabs.git
cd video_inlligence_twelvelabs
cp .env.example .env
# Fill in: TWELVELABS_API_KEY, ANTHROPIC_API_KEY, NEO4J_PASSWORD
docker compose up -d
sleep 30
curl http://localhost:8008/health
open http://localhost:3000
```

---

## 📡 Key API Endpoints
```bash
# Archive Search
POST /search/semantic
{"query": "news anchor delivering breaking news urgently", "use_twelvelabs": true}

# Segmentation  
POST /segment/analyze/{video_id}?content_type=news
GET  /segment/ad-breaks?limit=20
GET  /segment/export/{video_id}?format=json|xml|edl|csv

# Compliance
POST /compliance/check/{video_id}/explain?ruleset=broadcast_standards
```

---

Built for **NAB 2026 Hackathon** by **AdaBoost AI** (adaboost.io)

*TwelveLabs × Neo4j × ZeroClick.ai × Anthropic × Circle USDC × LTX Studio × TrackIt*
