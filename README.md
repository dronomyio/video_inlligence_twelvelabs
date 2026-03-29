# Archive Search Platform — NAB 2026

**TwelveLabs Marengo (AWS Bedrock) × Neo4j × Anthropic Opus 4.6 × TrackIt × Circle USDC**

> Transform dormant broadcast archives into queryable, monetizable assets.
> Find any moment in petabytes of footage using natural language — in seconds.

---

## Quick start

```bash
cp .env.example .env        # add AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY + ANTHROPIC_API_KEY
docker compose up -d --build
./start.sh pipeline         # index 500 archive videos
./start.sh test             # smoke test all 47 endpoints
```

| URL | Service |
|-----|---------|
| http://localhost:3008 | Archive Search UI |
| http://localhost:8008/docs | API (47 endpoints) |
| http://localhost:7477 | Neo4j Browser |

---

## Example queries

- "emotional celebration after a game-winning moment"
- "wide establishing shots of urban skylines at golden hour"
- "interview segments with outdoor natural lighting"
- "fast-paced action with quick cuts and dynamic camera movement"
- "sunset over water with birds flying"

---

## Key credentials

| Key | Required | Purpose |
|-----|----------|---------|
| `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` | ✅ Primary | TwelveLabs Marengo via Bedrock |
| `TWELVELABS_API_KEY` | Fallback | Direct API if no AWS creds |
| `ANTHROPIC_API_KEY` | ✅ Required | Opus 4.6 reasoning |
| `LTX_API_KEY` | Optional | AI clip preview generation |
| `TRACKIT_API_KEY` | Optional | SMPTE MAM integration |
| `CIRCLE_API_KEY` | Optional | USDC x402 micropayments |

---

## Business value

- Reduces asset search: **8 hours → 12 seconds**
- Eliminates external licensing: **$500–5K per clip → $0**
- Auto-metadata tagging: **$75–150K/FTE/year → $0 marginal cost**
- ROI: **8,888% in year one** for a 50TB broadcaster archive

See `docs/BUSINESS_CASE.md` for full quantification.

---

## Architecture

```
Archive Videos (sports / news / B-roll / documentary)
    ↓
TwelveLabs Marengo via AWS Bedrock (visual + audio + temporal)
    ↓
Neo4j Knowledge Graph (13 node types, semantic relationships)
    ↓
Opus 4.6 (similarity reasoning, archive curation)
    ↓
Archive Search API (47 endpoints, x402 USDC gated)
    ↓
TrackIt SMPTE MAM export + CDN delivery
```
