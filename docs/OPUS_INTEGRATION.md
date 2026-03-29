# Opus 4.6 Integration Guide

## Where Opus 4.6 runs in this system

Three jobs — all requiring cross-document reasoning across 500+ videos:

```
POST /ontology/infer     → Opus reads full corpus, proposes schema extensions
POST /campaigns/match    → Opus ranks inventory against advertiser brief  
POST /trends/detect      → Opus identifies emerging viral patterns week-over-week
```

All three use extended thinking (`"thinking": {"type": "enabled", "budget_tokens": 8000}`)
for the campaign matcher — the hardest ranking task.

---

## 1. Ontology Inference — `POST /ontology/infer`

### When to call it
- After the initial 500-video ingestion completes
- Weekly, as new content is ingested
- Any time you want Opus to discover new node types

### What it does
Opus receives:
- The current Neo4j schema (8 node types, 10 relationship types)
- Up to 500 raw scene labels from TwelveLabs Pegasus
- Top 100 trending hashtags from the graph
- Top 50 highest-performing hook segments

It reasons across all of this and returns a structured patch:

```json
{
  "new_node_types": [
    {
      "label": "ViralFormat",
      "description": "Recurring structural pattern correlated with virality",
      "properties": ["name", "pattern_description", "avg_viral_score"],
      "cypher_example": "MERGE (:ViralFormat {name: 'face_product_hook_2s'})",
      "advertiser_value": "Videos using this format have 2.3x higher ad recall"
    }
  ],
  "new_relationships": [
    {
      "type": "USES_FORMAT",
      "from": "Video",
      "to": "ViralFormat",
      "properties": ["confidence"],
      "advertiser_value": "Lets buyers filter inventory by proven viral format"
    }
  ],
  "schema_cypher_patch": "CREATE CONSTRAINT ...",
  "reasoning_summary": "The corpus shows 3 dominant hook patterns not in the schema..."
}
```

The patch is applied to Neo4j automatically. New `ViralFormat` nodes appear
immediately in the graph and can be queried:

```cypher
MATCH (v:Video)-[r:USES_FORMAT]->(f:ViralFormat)
WHERE f.avg_viral_score > 0.8
RETURN f.name, count(v) as video_count, f.advertiser_value
ORDER BY video_count DESC
```

### Cost estimate
~1 Opus call per batch = ~$0.50–$2.00 per week depending on corpus size.

---

## 2. Campaign Matching — `POST /campaigns/match`

### When to call it
- When an advertiser submits a campaign brief
- On-demand from the Campaigns UI page
- Via the API from an external CRM or ad ops system

### Request shape
```json
{
  "name": "HexClad Q2 Cookware",
  "advertiser": "HexClad",
  "vertical": "kitchenware",
  "target_audience": "food enthusiasts 25-44",
  "budget_usd": 10000,
  "max_cpm": 4.50,
  "brand_safety_level": "standard",
  "preferred_categories": ["food_cooking"],
  "ad_format": "both",
  "campaign_objective": "awareness",
  "activate_on_networks": true,
  "networks": ["gam", "ttd"]
}
```

### What Opus receives
- The full campaign brief above
- Top 100 videos by viral score with their scene data and brief CPMs
- All high/critical compliance flags (for exclusion logic)

### What Opus returns
```json
{
  "campaign_summary": "...",
  "total_estimated_reach": 8400000,
  "total_estimated_spend": 9250.00,
  "weighted_audience_match": 0.87,
  "placements": [
    {
      "rank": 1,
      "video_id": "abc123",
      "video_title": "Perfect pasta carbonara in 60s",
      "timestamp_seconds": 12.1,
      "ad_format": "6s_bumper",
      "audience_match_score": 0.94,
      "estimated_reach": 1800000,
      "estimated_cpm": 4.15,
      "estimated_spend": 747.00,
      "reasoning": "Highest food/cookware alignment in corpus. Dish reveal at 12.1s is the peak attention moment. Creator shows cookware prominently. Audience skews 28-42 food enthusiasts matching brief exactly.",
      "caveats": "None",
      "zeroclick_signal": "cookware_reveal_moment_high_attention"
    }
  ],
  "placements_excluded": [
    {
      "video_id": "xyz789",
      "reason": "compliance flag: violence severity high"
    }
  ],
  "executive_summary": "Found 18 brand-safe placements reaching 8.4M food enthusiasts..."
}
```

### Extended thinking
The campaign matcher uses `thinking: {type: "enabled", budget_tokens: 8000}`.
This gives Opus internal scratchpad space to reason through the ranking
before producing output — critical for getting the right order across
100 inventory items. Response time: 30–90 seconds.

### Cost estimate
~$3–8 per campaign match call (Opus with extended thinking on a large context).
At 10 campaigns/month = ~$50–80/month. Revenue per campaign: $2,000–$10,000.

---

## 3. Trend Detection — `POST /trends/detect`

### When to call it
- Daily automated job (add to worker.py scheduler)
- On-demand from API or a weekly newsletter workflow

### What it returns
```json
{
  "trend_report": {
    "trends": [
      {
        "name": "Sound-off product revelation",
        "description": "Videos where product is revealed visually with no creator voiceover, relying purely on reaction and text overlay",
        "evidence": ["43 new videos this week use this pattern", "avg viral score 0.84 vs 0.61 baseline"],
        "velocity_score": 0.91,
        "advertiser_verticals": ["ecommerce", "consumer_electronics"],
        "placement_strategy": "6-second bumper immediately before the reveal moment",
        "window_to_act": "48-72 hours before format saturates"
      }
    ],
    "executive_brief": "Three emerging formats identified this week..."
  }
}
```

This output is the weekly intelligence report product — $500–$2K/month
subscription for agencies and brand teams.

---

## Model selection rationale

| Task | Model | Why not Sonnet? |
|------|-------|----------------|
| Ontology inference | Opus 4.6 | Must reason across 500 scene labels simultaneously |
| Campaign matching | Opus 4.6 + thinking | Ranking 100 items requires holding full context |
| Trend detection | Opus 4.6 | Pattern detection across corpus delta |
| Brief copy | Sonnet 4.6 | Single-video task, fast is better |
| Compliance explain | Sonnet 4.6 | Well-defined task, no cross-reasoning |
| Metadata tagging | Haiku | High volume (5,000+/day), simple extraction |

---

## Adding ANTHROPIC_API_KEY

```bash
# In .env
ANTHROPIC_API_KEY=sk-ant-api03-...

# Verify it works
curl -X POST http://localhost:8000/ontology/infer
# Should return a patch with new_node_types array
```

If the key is missing, all three endpoints return HTTP 400 with a clear
message rather than silently failing.
