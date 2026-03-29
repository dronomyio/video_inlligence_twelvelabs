"""
ZeroClick.ai integration: generates zero-click advertiser briefs
from TwelveLabs-extracted context + Neo4j graph signals.
"""
import httpx
from typing import Dict, Any, Optional, List
from config import settings
import structlog

logger = structlog.get_logger()

ZEROCLICK_BASE = "https://api.zeroclick.ai/v1"


class ZeroClickService:
    def __init__(self):
        self.api_key = settings.zeroclick_api_key

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ── Generate Advertiser Brief ─────────────────────────────────────────────
    async def generate_brief(
        self,
        video_meta: Dict[str, Any],
        tl_context: Dict[str, Any],
        segments: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Sends video intelligence to ZeroClick.ai to generate a
        contextual advertiser brief with zero-click placement recommendation.

        Falls back to local generation if ZeroClick API key not set.
        """
        if not self.api_key or self.api_key == "your_zeroclick_api_key_here":
            return self._local_brief_fallback(video_meta, tl_context, segments)

        # Find best placement moment (hook with highest viral_segment_score)
        hook_segments = [s for s in segments if s.get("segment_type") == "hook"]
        best_segment = max(
            hook_segments or segments,
            key=lambda s: s.get("viral_segment_score", 0),
            default={}
        )

        payload = {
            "context": {
                "title": video_meta.get("title", ""),
                "category": video_meta.get("category", ""),
                "view_count": video_meta.get("view_count", 0),
                "viral_score": video_meta.get("viral_score", 0),
                "mood": tl_context.get("mood", ""),
                "key_objects": tl_context.get("key_objects", []),
                "audience_signals": tl_context.get("audience_signals", ""),
                "brand_safe": tl_context.get("brand_safe", True),
                "best_placement_time": tl_context.get("best_placement_time", 0),
                "placement_recommendation": tl_context.get("placement_recommendation", ""),
            },
            "advertiser_verticals": video_meta.get("advertiser_verticals", []),
            "format": "short_brief",
            "include_cpm_estimate": True,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{ZEROCLICK_BASE}/briefs/generate",
                    headers=self._headers(),
                    json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "headline": data.get("headline", ""),
                        "placement_moment": best_segment.get("t_start", 0),
                        "target_verticals": video_meta.get("advertiser_verticals", []),
                        "estimated_cpm": data.get("estimated_cpm", 0),
                        "zeroclick_context": data.get("context_summary", ""),
                    }
                logger.warning("zeroclick_api_error", status=resp.status_code)
        except Exception as e:
            logger.error("zeroclick_request_failed", error=str(e))

        return self._local_brief_fallback(video_meta, tl_context, segments)

    def _local_brief_fallback(
        self,
        video_meta: Dict[str, Any],
        tl_context: Dict[str, Any],
        segments: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Local brief generation when ZeroClick API unavailable.
        Uses the same logic structure as the remote call.
        """
        category = video_meta.get("category", "general")
        view_count = video_meta.get("view_count", 0)
        viral_score = video_meta.get("viral_score", 0.5)
        verticals = video_meta.get("advertiser_verticals", ["general"])
        mood = tl_context.get("mood", "engaging")
        objects = tl_context.get("key_objects", [])
        brand_safe = tl_context.get("brand_safe", True)

        # Find best hook moment
        hook_segments = [s for s in segments if s.get("segment_type") == "hook"]
        best_t = 0
        if hook_segments:
            best_seg = max(hook_segments, key=lambda s: s.get("viral_segment_score", 0))
            best_t = best_seg.get("t_start", 0)

        # CPM tier
        cpm_map = {"food_cooking": 3.50, "product_unboxing": 4.00,
                   "sports_highlights": 3.80, "satisfying_asmr": 2.50,
                   "life_hack_tutorial": 3.20}
        base_cpm = cpm_map.get(category, 3.00)
        estimated_cpm = round(base_cpm * (0.7 + 0.6 * viral_score), 2)

        headline = (
            f"{mood.title()} {category.replace('_', ' ')} content — "
            f"{view_count:,} views, viral score {viral_score:.2f}. "
            f"Ideal for {', '.join(verticals[:2])} advertisers."
        )

        objects_str = ", ".join(objects[:3]) if objects else "engaging visual content"
        zeroclick_ctx = (
            f"Brand-safe: {brand_safe}. "
            f"Key objects: {objects_str}. "
            f"Best pre-roll placement at {best_t:.1f}s (peak attention). "
            f"Recommended format: 6-second bumper or 15-second pre-roll. "
            f"Target verticals: {', '.join(verticals)}."
        )

        return {
            "headline": headline,
            "placement_moment": best_t,
            "target_verticals": verticals,
            "estimated_cpm": estimated_cpm,
            "zeroclick_context": zeroclick_ctx,
        }

    # ── Batch Brief Generation ─────────────────────────────────────────────────
    async def generate_bulk_briefs(
        self, videos: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate briefs for multiple videos efficiently."""
        results = []
        for video in videos:
            brief = await self.generate_brief(
                video_meta=video,
                tl_context=video.get("tl_context", {}),
                segments=video.get("segments", []),
            )
            brief["video_id"] = video.get("video_id")
            results.append(brief)
        return results


zeroclick_service = ZeroClickService()
