"""
Opus 4.6 service — two high-cognition jobs:

1. Ontology inference: reads raw scene corpus, discovers emergent node
   types and relationships the hand-coded schema missed, returns
   Cypher MERGE patches ready to apply to Neo4j.

2. Campaign-to-inventory matching: takes an advertiser campaign brief,
   reasons across the full video graph, returns a ranked media plan
   with written rationale per placement — the product agencies pay for.

Uses Anthropic SDK directly so it can leverage extended thinking
on the campaign matcher (the hardest reasoning task).
"""
import json
import re
import httpx
from typing import Any, Dict, List, Optional
from config import settings
import structlog

logger = structlog.get_logger()

ANTHROPIC_BASE = "https://api.anthropic.com/v1"
OPUS_MODEL = "claude-opus-4-5"          # use claude-opus-4-5 (latest available)
SONNET_MODEL = "claude-sonnet-4-5"      # fallback for lighter tasks


def _headers() -> Dict[str, str]:
    return {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }


async def _call_claude(
    messages: List[Dict],
    system: str,
    model: str = OPUS_MODEL,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    use_thinking: bool = False,
) -> str:
    """Core async call to Anthropic messages API."""
    payload: Dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
    }
    if use_thinking:
        payload["thinking"] = {"type": "enabled", "budget_tokens": 8000}
        payload.pop("temperature", None)
    else:
        payload["temperature"] = temperature

    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            f"{ANTHROPIC_BASE}/messages",
            headers=_headers(),
            json=payload,
        )
        if resp.status_code != 200:
            logger.error("claude_api_error",
                         status=resp.status_code, body=resp.text[:300])
            return ""

        data = resp.json()
        # collect all text blocks (thinking blocks are separate)
        text_blocks = [
            b["text"] for b in data.get("content", [])
            if b.get("type") == "text"
        ]
        return "\n".join(text_blocks)


def _extract_json(text: str) -> Any:
    """Pull the first JSON object or array out of a text response."""
    # Try object first, then array
    for pattern in (r'\{.*\}', r'\[.*\]'):
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                continue
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 1.  ONTOLOGY INFERENCE
# ─────────────────────────────────────────────────────────────────────────────

ONTOLOGY_SYSTEM = """
You are a senior knowledge graph architect specialising in media intelligence
and advertising technology.

You will receive:
  - The current Neo4j schema (node labels, relationship types, properties)
  - A sample of raw scene labels extracted from 500 viral short-form videos
  - Aggregated tag and mood data from those videos

Your job is to reason deeply across the full corpus and return a structured
ontology patch — new node types, new relationship types, new properties, and
new Cypher MERGE statements — that would make this graph more useful for:
  (a) advertisers finding the best placement moments
  (b) detecting viral content patterns early
  (c) connecting similar content across categories

Rules:
- Only propose additions, never removals
- Every new node type needs a unique constraint
- Every new relationship needs a clear semantic meaning
- Provide example Cypher for each addition
- Explain WHY each addition improves advertiser targeting

Respond as a JSON object with this exact structure:
{
  "new_node_types": [
    {
      "label": "ViralFormat",
      "description": "...",
      "properties": ["name", "pattern_description", "avg_viral_score"],
      "unique_constraint_on": "name",
      "cypher_example": "MERGE (:ViralFormat {name: 'face_product_hook', ...})",
      "advertiser_value": "..."
    }
  ],
  "new_relationships": [
    {
      "type": "USES_FORMAT",
      "from": "Video",
      "to": "ViralFormat",
      "properties": ["confidence"],
      "cypher_example": "MATCH (v:Video),(f:ViralFormat) MERGE (v)-[:USES_FORMAT {confidence: 0.9}]->(f)",
      "advertiser_value": "..."
    }
  ],
  "new_video_properties": [
    {
      "name": "face_visible_hook",
      "type": "boolean",
      "description": "Creator face visible in first 2 seconds",
      "advertiser_value": "..."
    }
  ],
  "schema_cypher_patch": "-- full Cypher block to apply to Neo4j --",
  "reasoning_summary": "3-5 sentence explanation of the most important discovery"
}
"""


async def infer_ontology(
    current_schema: Dict[str, Any],
    scene_label_sample: List[str],
    tag_frequency: Dict[str, int],
    mood_distribution: Dict[str, int],
    top_hooks: List[Dict],
) -> Dict[str, Any]:
    """
    Call Opus 4.6 to reason across the corpus and propose ontology extensions.

    Returns the parsed JSON patch plus the raw reasoning text.
    """
    corpus_summary = {
        "current_schema": current_schema,
        "scene_labels_sample": scene_label_sample[:200],   # cap for context
        "top_100_tags": dict(sorted(
            tag_frequency.items(), key=lambda x: -x[1])[:100]),
        "mood_distribution": mood_distribution,
        "top_hook_patterns": top_hooks[:30],
    }

    user_msg = f"""
Here is the current graph state and corpus sample:

{json.dumps(corpus_summary, indent=2)}

Analyse this data carefully. Identify:
1. What content patterns are viral that the current schema cannot express?
2. What new node types would let advertisers find better placements?
3. What relationships between existing nodes are implied but not captured?

Return your full ontology patch as specified.
"""

    logger.info("ontology_inference_start",
                scenes=len(scene_label_sample), tags=len(tag_frequency))

    raw = await _call_claude(
        messages=[{"role": "user", "content": user_msg}],
        system=ONTOLOGY_SYSTEM,
        model=OPUS_MODEL,
        max_tokens=6000,
        temperature=0.2,
    )

    patch = _extract_json(raw)
    if not patch:
        logger.warning("ontology_json_parse_failed", raw_preview=raw[:200])
        patch = {"error": "parse_failed", "raw": raw[:500]}

    logger.info("ontology_inference_complete",
                new_nodes=len(patch.get("new_node_types", [])),
                new_rels=len(patch.get("new_relationships", [])))
    return {"patch": patch, "raw_reasoning": raw}


# ─────────────────────────────────────────────────────────────────────────────
# 2.  CAMPAIGN-TO-INVENTORY MATCHER
# ─────────────────────────────────────────────────────────────────────────────

CAMPAIGN_SYSTEM = """
You are a senior programmatic media planner with deep expertise in
contextual video advertising and short-form content monetisation.

You will receive:
  - An advertiser's campaign brief (budget, target audience, verticals,
    brand safety requirements, CPM ceiling, desired ad format)
  - A graph snapshot of available video inventory: videos with viral scores,
    scene segments with timestamps, advertiser briefs already generated,
    compliance flags, and creator data

Your job is to produce a ranked media plan: the top placement moments
across the inventory that best match the campaign brief.

For each placement you must provide:
  - Clear reasoning why this specific moment matches the brief
  - The exact timestamp to insert the ad
  - The predicted audience match score (0-1)
  - Whether to use a 6-second bumper or 15-second pre-roll
  - Any caveats (compliance flags, audience mismatch risks)

Think carefully. A bad media plan wastes the advertiser's budget.
Consider the full context: viral score, hook strength, category alignment,
mood match, brand safety, CPM vs budget ceiling.

Respond as a JSON object:
{
  "campaign_summary": "one sentence restatement of what this campaign needs",
  "total_estimated_reach": 1234567,
  "total_estimated_spend": 4500.00,
  "weighted_audience_match": 0.87,
  "placements": [
    {
      "rank": 1,
      "video_id": "...",
      "video_title": "...",
      "video_url": "...",
      "category": "...",
      "timestamp_seconds": 12.1,
      "ad_format": "6s_bumper",
      "audience_match_score": 0.94,
      "estimated_reach": 180000,
      "estimated_cpm": 4.15,
      "estimated_spend": 747.00,
      "reasoning": "...",
      "caveats": "...",
      "zeroclick_signal": "..."
    }
  ],
  "placements_excluded": [
    {
      "video_id": "...",
      "reason": "compliance flag: violence severity high"
    }
  ],
  "executive_summary": "3-4 sentence overview for the media buyer"
}
"""


async def match_campaign_to_inventory(
    campaign_brief: Dict[str, Any],
    inventory_snapshot: List[Dict[str, Any]],
    compliance_flags: List[Dict[str, Any]],
    top_n: int = 20,
) -> Dict[str, Any]:
    """
    Call Opus 4.6 with extended thinking to match a campaign brief
    against the full video inventory and return a ranked media plan.

    campaign_brief keys:
      name, advertiser, vertical, target_audience, budget_usd,
      max_cpm, brand_safety_level (strict|standard|relaxed),
      preferred_categories, ad_format (bumper|preroll|both),
      campaign_objective (awareness|consideration|conversion),
      start_date, end_date

    Returns parsed media plan + raw reasoning.
    """
    # Build flagged video set for exclusion logic
    flagged_video_ids = {
        f.get("v.video_id") or f.get("video_id")
        for f in compliance_flags
        if f.get("f.severity") in ("critical", "high")
    }

    # Limit inventory to top 100 by viral score to fit context window
    inventory_sorted = sorted(
        inventory_snapshot,
        key=lambda v: v.get("v.viral_score", 0),
        reverse=True
    )[:100]

    # Annotate each video with its compliance status
    for v in inventory_sorted:
        vid = v.get("v.video_id", "")
        v["compliance_status"] = "flagged" if vid in flagged_video_ids else "clean"

    user_msg = f"""
CAMPAIGN BRIEF:
{json.dumps(campaign_brief, indent=2)}

AVAILABLE INVENTORY ({len(inventory_sorted)} videos, ranked by viral score):
{json.dumps(inventory_sorted, indent=2)}

COMPLIANCE FLAGS (high/critical severity):
{json.dumps([f for f in compliance_flags if f.get("f.severity") in ("critical","high")], indent=2)}

Instructions:
- Select the top {top_n} placement moments that best serve this campaign
- Exclude any video with compliance_status = "flagged" unless brand_safety_level = "relaxed"
- Respect the max_cpm ceiling: {campaign_brief.get('max_cpm', 5.0)}
- Prefer videos in: {campaign_brief.get('preferred_categories', 'any')}
- Target audience: {campaign_brief.get('target_audience', 'general')}
- Total budget: ${campaign_brief.get('budget_usd', 5000)}

Think step by step before producing the final ranked list.
"""

    logger.info("campaign_match_start",
                advertiser=campaign_brief.get("advertiser"),
                budget=campaign_brief.get("budget_usd"),
                inventory_size=len(inventory_sorted))

    raw = await _call_claude(
        messages=[{"role": "user", "content": user_msg}],
        system=CAMPAIGN_SYSTEM,
        model=OPUS_MODEL,
        max_tokens=8000,
        use_thinking=True,   # extended thinking for ranking quality
    )

    plan = _extract_json(raw)
    if not plan:
        logger.warning("campaign_json_parse_failed", raw_preview=raw[:200])
        plan = {"error": "parse_failed", "raw": raw[:500]}

    logger.info("campaign_match_complete",
                placements=len(plan.get("placements", [])),
                reach=plan.get("total_estimated_reach", 0))
    return {"media_plan": plan, "raw_reasoning": raw}


# ─────────────────────────────────────────────────────────────────────────────
# 3.  TREND EMERGENCE DETECTOR  (bonus Opus job)
# ─────────────────────────────────────────────────────────────────────────────

TREND_SYSTEM = """
You are a viral content trend analyst for a media intelligence platform.

You receive weekly snapshots of a video graph — scene labels, tag frequencies,
hook patterns — and identify which NEW trends are emerging this week that
were not present or were weaker last week.

For each trend provide:
- A clear name and description
- Evidence from the data (specific labels, tags, view velocity)
- A velocity score (0-1): how fast is this trend growing?
- Which advertiser verticals should act on this NOW
- A recommended ad format and placement strategy

Respond as JSON:
{
  "report_date": "...",
  "trends": [
    {
      "name": "...",
      "description": "...",
      "evidence": ["...", "..."],
      "velocity_score": 0.87,
      "advertiser_verticals": ["CPG", "kitchenware"],
      "placement_strategy": "...",
      "window_to_act": "48-72 hours before saturation"
    }
  ],
  "executive_brief": "..."
}
"""


async def detect_trends(
    current_week_data: Dict[str, Any],
    previous_week_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Daily/weekly trend emergence detection using Opus."""
    user_msg = f"""
CURRENT WEEK corpus snapshot:
{json.dumps(current_week_data, indent=2)}

PREVIOUS WEEK corpus snapshot (baseline):
{json.dumps(previous_week_data, indent=2)}

Identify the 3-5 most significant emerging trends.
Focus on patterns that are NEW or accelerating, not established baselines.
"""
    raw = await _call_claude(
        messages=[{"role": "user", "content": user_msg}],
        system=TREND_SYSTEM,
        model=OPUS_MODEL,
        max_tokens=4000,
        temperature=0.3,
    )
    report = _extract_json(raw)
    if not report:
        report = {"error": "parse_failed", "raw": raw[:500]}
    return {"trend_report": report, "raw_reasoning": raw}


opus_service = {
    "infer_ontology": infer_ontology,
    "match_campaign": match_campaign_to_inventory,
    "detect_trends": detect_trends,
}
