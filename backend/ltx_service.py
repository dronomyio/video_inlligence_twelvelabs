"""
LTX AI creative generation service.

LTX (ltx.ai) is production-ready creative infrastructure for enterprises and
studios. Given a ZeroClick advertiser brief + TwelveLabs scene context, this
service calls the LTX API to generate a matching video ad creative:
  - 6-second bumper matched to scene mood, palette, objects
  - 15-second pre-roll with brand-aligned visuals
  - Static thumbnail for display inventory

Flow:
  TwelveLabs context (mood, objects, palette, timestamp)
      ↓
  LTX prompt construction
      ↓
  LTX video generation API (async, poll for completion)
      ↓
  Creative stored in Neo4j (:Creative) node
      ↓
  Creative ID returned to GAM/TTD for ad serving

Falls back gracefully when LTX_API_KEY not set — returns a simulated
creative URL so the full pipeline demo works without credentials.
"""

import asyncio
import uuid
import time
from typing import Any, Dict, List, Optional

import httpx

from config import settings
import structlog

logger = structlog.get_logger()

LTX_BASE = "https://api.ltx.studio/v1"


def _ltx_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.ltx_api_key}",
        "Content-Type": "application/json",
    }


# ── Prompt builder ────────────────────────────────────────────────────────────

def build_ltx_prompt(
    brief: Dict[str, Any],
    tl_context: Dict[str, Any],
    video_meta: Dict[str, Any],
    ad_format: str = "6s_bumper",
) -> str:
    """
    Translate ZeroClick brief + TwelveLabs context into an LTX generation prompt.
    Designed to produce a creative that visually matches the placement moment.
    """
    mood        = tl_context.get("mood", "engaging")
    objects     = tl_context.get("key_objects", [])
    audience    = tl_context.get("audience_signals", "general audience")
    category    = video_meta.get("v.category", "").replace("_", " ")
    verticals   = brief.get("target_verticals", [])
    cta         = brief.get("ab.headline", "")
    placement_t = float(brief.get("ab.placement_moment", 0))

    objects_str   = ", ".join(objects[:4]) if objects else "the product"
    verticals_str = " and ".join(verticals[:2]) if verticals else "consumer"

    duration_map = {
        "6s_bumper":  "6-second",
        "15s_preroll": "15-second",
        "thumbnail":   "single frame",
    }
    duration = duration_map.get(ad_format, "6-second")

    prompt = (
        f"Create a {duration} video advertisement for a {verticals_str} brand. "
        f"Visual style: {mood}, warm and professional. "
        f"Featured elements: {objects_str}. "
        f"Target audience: {audience}. "
        f"Context: this ad appears at {placement_t:.1f}s in a viral {category} video. "
        f"The creative must visually match the surrounding content's energy and palette. "
        f"Call to action: {cta}. "
        f"Production quality: broadcast-ready, no watermarks, clean composition. "
        f"Format: vertical 9:16 for mobile-first placement."
    )
    return prompt


# ── LTX Service ───────────────────────────────────────────────────────────────

class LTXService:
    """
    Calls LTX Studio API to generate video ad creatives from
    ZeroClick briefs. Supports 6s bumpers, 15s pre-rolls, and thumbnails.
    """

    def __init__(self):
        self.enabled = bool(settings.ltx_api_key)

    # ── Generation ────────────────────────────────────────────────────────────
    async def generate_creative(
        self,
        brief: Dict[str, Any],
        tl_context: Dict[str, Any],
        video_meta: Dict[str, Any],
        ad_format: str = "6s_bumper",
    ) -> Dict[str, Any]:
        """
        Generate a video creative matched to the placement brief.
        Returns creative_id, video_url, thumbnail_url, generation metadata.
        """
        if not self.enabled:
            return self._sim_creative(brief, video_meta, ad_format)

        prompt = build_ltx_prompt(brief, tl_context, video_meta, ad_format)

        duration_seconds = 6 if "6s" in ad_format else 15

        payload = {
            "prompt": prompt,
            "duration": duration_seconds,
            "resolution": "720p",
            "aspect_ratio": "9:16",
            "quality": "high",
            "output_format": "mp4",
            "metadata": {
                "video_id":   video_meta.get("v.video_id", ""),
                "category":   video_meta.get("v.category", ""),
                "ad_format":  ad_format,
                "brief_cpm":  brief.get("ab.estimated_cpm", 0),
            },
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{LTX_BASE}/generations",
                headers=_ltx_headers(),
                json=payload,
            )
            if resp.status_code not in (200, 201):
                logger.error("ltx_generation_failed",
                             status=resp.status_code, body=resp.text[:200])
                return self._sim_creative(brief, video_meta, ad_format)

            data    = resp.json()
            task_id = data.get("id") or data.get("task_id")
            if not task_id:
                return self._sim_creative(brief, video_meta, ad_format)

        result = await self._poll_generation(task_id)
        if not result:
            return self._sim_creative(brief, video_meta, ad_format)

        creative_id = f"ltx_{uuid.uuid4().hex[:12]}"
        logger.info("ltx_creative_generated",
                    creative_id=creative_id, ad_format=ad_format)
        return {
            "creative_id":    creative_id,
            "task_id":        task_id,
            "video_url":      result.get("video_url", ""),
            "thumbnail_url":  result.get("thumbnail_url", ""),
            "duration":       duration_seconds,
            "ad_format":      ad_format,
            "prompt":         prompt,
            "status":         "ready",
            "provider":       "ltx",
            "generated_at":   int(time.time()),
        }

    async def _poll_generation(
        self,
        task_id: str,
        max_wait: int = 300,
    ) -> Optional[Dict[str, Any]]:
        """Poll LTX task until video is ready (max 5 min)."""
        start = time.time()
        async with httpx.AsyncClient(timeout=20) as client:
            while time.time() - start < max_wait:
                resp = await client.get(
                    f"{LTX_BASE}/generations/{task_id}",
                    headers=_ltx_headers(),
                )
                if resp.status_code == 200:
                    data   = resp.json()
                    status = data.get("status", "")
                    if status in ("completed", "ready", "succeeded"):
                        return data
                    if status in ("failed", "error"):
                        logger.error("ltx_task_failed", task_id=task_id, data=data)
                        return None
                await asyncio.sleep(8)
        logger.error("ltx_poll_timeout", task_id=task_id)
        return None

    # ── Batch generation ──────────────────────────────────────────────────────
    async def generate_campaign_creatives(
        self,
        placements: List[Dict[str, Any]],
        ad_format: str = "6s_bumper",
    ) -> List[Dict[str, Any]]:
        """
        Generate one creative per Opus-ranked placement.
        Called after /campaigns/match to produce a full creative set.
        """
        results = []
        for p in placements[:10]:   # cap at 10 to manage generation time
            brief = {
                "target_verticals":  p.get("verticals", []),
                "ab.estimated_cpm":  p.get("estimated_cpm", 3.0),
                "ab.placement_moment": p.get("timestamp_seconds", 0),
                "ab.headline":       p.get("reasoning", "")[:80],
            }
            tl_ctx = {
                "mood":            p.get("mood", "engaging"),
                "key_objects":     p.get("key_objects", []),
                "audience_signals": p.get("audience_match_score", 0),
            }
            video_meta = {
                "v.video_id":  p.get("video_id", ""),
                "v.category":  p.get("category", ""),
                "v.viral_score": p.get("audience_match_score", 0),
            }
            creative = await self.generate_creative(brief, tl_ctx, video_meta, ad_format)
            creative["video_id"] = p.get("video_id", "")
            creative["rank"]     = p.get("rank", 0)
            results.append(creative)

        logger.info("ltx_batch_complete", count=len(results))
        return results

    # ── Thumbnail only ────────────────────────────────────────────────────────
    async def generate_thumbnail(
        self,
        brief: Dict[str, Any],
        tl_context: Dict[str, Any],
        video_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a static thumbnail for display ad inventory."""
        return await self.generate_creative(brief, tl_context, video_meta, "thumbnail")

    # ── Simulation ────────────────────────────────────────────────────────────
    def _sim_creative(
        self,
        brief: Dict[str, Any],
        video_meta: Dict[str, Any],
        ad_format: str,
    ) -> Dict[str, Any]:
        creative_id = f"ltx_sim_{uuid.uuid4().hex[:10]}"
        category    = video_meta.get("v.category", "general")
        cpm         = brief.get("ab.estimated_cpm", 3.0)
        duration    = 6 if "6s" in ad_format else 15

        logger.info("ltx_simulated_creative", creative_id=creative_id)
        return {
            "creative_id":   creative_id,
            "task_id":       f"task_{uuid.uuid4().hex[:8]}",
            "video_url":     f"https://ltx.studio/simulated/{creative_id}.mp4",
            "thumbnail_url": f"https://ltx.studio/simulated/{creative_id}.jpg",
            "duration":      duration,
            "ad_format":     ad_format,
            "prompt":        build_ltx_prompt(brief, {}, video_meta, ad_format),
            "status":        "simulated",
            "provider":      "ltx",
            "category":      category,
            "estimated_cpm": cpm,
            "generated_at":  int(time.time()),
            "note":          "Set LTX_API_KEY in .env to generate real creatives",
        }


ltx_service = LTXService()
