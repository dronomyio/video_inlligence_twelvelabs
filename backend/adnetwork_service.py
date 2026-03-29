"""
Ad Network Integration — Path A revenue layer.

Connects ZeroClick briefs to two demand-side platforms:
  1. Google Ad Manager (GAM) — via Display & Video 360 API
  2. The Trade Desk (TTD) — via OpenRTB 2.6 + TTD Bid Manager API

Flow:
  ZeroClick brief → contextual targeting object → DSP line item / deal ID
  → impressions served → revenue reported back → Neo4j updated

For the hackathon/MVP this module does three things:
  A. Translates a ZeroClick brief into GAM/TTD targeting parameters
  B. Creates a private marketplace (PMP) deal or direct line item
  C. Polls for impression/spend data and writes it back to Neo4j

Both DSP integrations fall back gracefully when API keys are not set —
they return simulated responses so the UI always has data to show.
"""
import asyncio
import httpx
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from config import settings
import structlog

logger = structlog.get_logger()


# ─────────────────────────────────────────────────────────────────────────────
# Config helpers
# ─────────────────────────────────────────────────────────────────────────────

def _gam_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.gam_access_token}",
        "Content-Type": "application/json",
    }

async def _refresh_gam_token() -> Optional[str]:
    """
    Auto-refresh the GAM OAuth2 access token using the stored refresh token.
    Call this when a GAM request returns 401.
    Updates settings.gam_access_token in-place for the process lifetime.
    """
    if not (settings.gam_refresh_token and settings.gam_client_id and settings.gam_client_secret):
        logger.warning("gam_oauth_refresh_missing_credentials")
        return None

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type":    "refresh_token",
                "refresh_token": settings.gam_refresh_token,
                "client_id":     settings.gam_client_id,
                "client_secret": settings.gam_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code == 200:
            token_data = resp.json()
            new_token = token_data.get("access_token")
            if new_token:
                # Patch settings at runtime so all subsequent requests use the new token
                settings.gam_access_token = new_token
                logger.info("gam_token_refreshed")
                return new_token
        logger.error("gam_token_refresh_failed",
                     status=resp.status_code, body=resp.text[:200])
    return None

def _ttd_headers() -> Dict[str, str]:
    return {
        "TTD-Auth": settings.ttd_api_key,
        "Content-Type": "application/json",
    }

GAM_BASE = "https://googleads.googleapis.com/v17"
TTD_BASE = "https://api.thetradedesk.com/v3"


# ─────────────────────────────────────────────────────────────────────────────
# Brief → Targeting translation
# ─────────────────────────────────────────────────────────────────────────────

VERTICAL_TO_IAB = {
    "CPG":                  ["IAB1", "IAB8"],           # Food, Food & Drink
    "kitchenware":          ["IAB8", "IAB26"],           # Food, Tech
    "delivery_apps":        ["IAB8-5"],                  # Restaurant
    "ecommerce":            ["IAB22"],                   # Shopping
    "consumer_electronics": ["IAB26"],                   # Technology
    "fashion":              ["IAB18"],                   # Style & Fashion
    "sports_brands":        ["IAB17"],                   # Sports
    "energy_drinks":        ["IAB17", "IAB8"],
    "fitness":              ["IAB17-20"],                # Running/fitness
    "wellness":             ["IAB7"],                    # Health & Fitness
    "SaaS":                 ["IAB26-4"],                 # Software
    "education":            ["IAB5"],
    "home_improvement":     ["IAB10"],                   # Home & Garden
    "beauty":               ["IAB18-1"],                 # Beauty
    "mindfulness":          ["IAB7-37"],                 # Yoga
}

CATEGORY_TO_CONTENT_LABEL = {
    "food_cooking":       "cooking,food,recipe,transformation",
    "product_unboxing":   "unboxing,product,review,reveal",
    "sports_highlights":  "sports,athletic,highlight,competition",
    "satisfying_asmr":    "satisfying,asmr,relaxing,sensory",
    "life_hack_tutorial": "tutorial,hack,howto,skill,educational",
}


def brief_to_gam_targeting(brief: Dict[str, Any], video_meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a ZeroClick brief into a Google Ad Manager targeting spec.
    Uses contextual keywords + custom key-values for moment-level targeting.
    """
    verticals  = brief.get("target_verticals", [])
    category   = video_meta.get("v.category", "")
    viral_score = float(video_meta.get("v.viral_score", 0))
    placement_t = float(brief.get("ab.placement_moment", 0))

    iab_cats = []
    for v in verticals:
        iab_cats.extend(VERTICAL_TO_IAB.get(v, []))

    content_keywords = CATEGORY_TO_CONTENT_LABEL.get(category, "").split(",")

    return {
        "targeting": {
            "inventoryTargeting": {
                "targetedAdUnits": [],          # populated with actual ad unit IDs
            },
            "customCriteriaTargeting": {
                "keyValuePairs": [
                    {
                        "key": "viral_score_tier",
                        "values": ["high" if viral_score > 0.7 else "medium"],
                    },
                    {
                        "key": "content_category",
                        "values": [category],
                    },
                    {
                        "key": "placement_timestamp",
                        "values": [f"{int(placement_t)}s"],
                    },
                    {
                        "key": "advertiser_vertical",
                        "values": verticals[:3],
                    },
                ]
            },
            "contentTargeting": {
                "targetedContentKeywords": content_keywords,
            },
            "technologyTargeting": {
                "deviceCategoryTargeting": {
                    "targetedDeviceCategories": [
                        {"id": 30000},   # mobile
                        {"id": 30001},   # tablet
                    ]
                }
            }
        },
        "iab_categories": list(set(iab_cats)),
        "estimated_cpm_micros": int(float(brief.get("ab.estimated_cpm", 3.0)) * 1_000_000),
    }


def brief_to_ttd_deal(brief: Dict[str, Any], video_meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a ZeroClick brief into a Trade Desk Private Marketplace deal spec.
    """
    verticals   = brief.get("target_verticals", [])
    category    = video_meta.get("v.category", "")
    cpm         = float(brief.get("ab.estimated_cpm", 3.0))
    view_count  = int(video_meta.get("v.view_count", 0))

    iab_cats = []
    for v in verticals:
        iab_cats.extend(VERTICAL_TO_IAB.get(v, []))

    return {
        "DealId": f"viral-intel-{uuid.uuid4().hex[:12]}",
        "Name": f"Viral Intel | {category} | {video_meta.get('v.video_id','')}",
        "Description": brief.get("ab.headline", ""),
        "FloorCPM": cpm * 0.8,          # floor at 80% of estimated CPM
        "TargetCPM": cpm,
        "Availability": "PMP",          # Private Marketplace
        "Currency": "USD",
        "StartDateInclusive": datetime.now(timezone.utc).isoformat(),
        "EndDateExclusive": (
            datetime.now(timezone.utc) + timedelta(days=30)
        ).isoformat(),
        "InventoryAttributes": {
            "SupplyType": "mobile_app",
            "PlacementType": "in_stream_video",
            "VideoPlayerSize": "large",
        },
        "Targeting": {
            "ContentCategories": list(set(iab_cats)),
            "Keywords": CATEGORY_TO_CONTENT_LABEL.get(category, "").split(","),
            "CustomAudienceContextualSignals": {
                "ViralScore":       video_meta.get("v.viral_score", 0),
                "PlacementOffset":  brief.get("ab.placement_moment", 0),
                "Category":         category,
                "Verticals":        verticals,
            }
        },
        "EstimatedImpressions": view_count,
        "ZeroClickContext":      brief.get("ab.zeroclick_context", ""),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Google Ad Manager API calls
# ─────────────────────────────────────────────────────────────────────────────

class GAMService:
    """
    Google Ad Manager integration.
    Creates line items with contextual targeting from ZeroClick briefs.
    """

    def __init__(self):
        self.network_code = settings.gam_network_code
        self.enabled = (
            settings.enable_gam
            and bool(settings.gam_access_token and settings.gam_network_code)
        )
        if not settings.enable_gam:
            logger.info("gam_disabled_by_flag")

    async def create_line_item(
        self,
        brief: Dict[str, Any],
        video_meta: Dict[str, Any],
        order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a GAM line item for a ZeroClick brief placement."""
        if not self.enabled:
            return self._simulate_line_item(brief, video_meta)

        targeting = brief_to_gam_targeting(brief, video_meta)

        payload = {
            "name": f"ViralIntel | {video_meta.get('v.video_id','')} | {datetime.now().strftime('%Y%m%d')}",
            "orderId": order_id,
            "lineItemType": "STANDARD",
            "startDateTime": {"timeZoneId": "America/New_York"},
            "endDateTime": {
                "date": {"year": 2026, "month": 12, "day": 31},
                "timeZoneId": "America/New_York",
            },
            "costType": "CPM",
            "costPerUnit": {
                "currencyCode": "USD",
                "microAmount": targeting["estimated_cpm_micros"],
            },
            "primaryGoal": {
                "goalType": "IMPRESSIONS",
                "unitType": "IMPRESSIONS",
                "units": int(video_meta.get("v.view_count", 100000) * 0.1),
            },
            "targeting": targeting["targeting"],
            "creativePlaceholders": [
                {
                    "size": {"width": 640, "height": 480},
                    "creativeSizeType": "VIDEO_PLAYER_SIZING",
                }
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{GAM_BASE}/networks/{self.network_code}/lineItems",
                    headers=_gam_headers(),
                    json=payload,
                )
                # Auto-refresh token if expired
                if resp.status_code == 401:
                    logger.info("gam_401_refreshing_token")
                    new_token = await _refresh_gam_token()
                    if new_token:
                        resp = await client.post(
                            f"{GAM_BASE}/networks/{self.network_code}/lineItems",
                            headers=_gam_headers(),
                            json=payload,
                        )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    logger.info("gam_line_item_created",
                                line_item_id=data.get("id"))
                    return {
                        "status": "created",
                        "platform": "google_ad_manager",
                        "line_item_id": data.get("id"),
                        "targeting_summary": targeting,
                    }
                else:
                    logger.error("gam_create_failed",
                                 status=resp.status_code, body=resp.text[:200])
        except Exception as e:
            logger.error("gam_request_error", error=str(e))

        return self._simulate_line_item(brief, video_meta)

    async def get_delivery_stats(self, line_item_id: str) -> Dict[str, Any]:
        """Poll GAM for impressions and revenue on a line item."""
        if not self.enabled:
            return self._simulate_stats()

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    f"{GAM_BASE}/networks/{self.network_code}/lineItems/{line_item_id}/stats",
                    headers=_gam_headers(),
                )
                if resp.status_code == 401:
                    await _refresh_gam_token()
                    resp = await client.get(
                        f"{GAM_BASE}/networks/{self.network_code}/lineItems/{line_item_id}/stats",
                        headers=_gam_headers(),
                    )
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.error("gam_stats_error", error=str(e))

        return self._simulate_stats()

    def _simulate_line_item(self, brief, video_meta) -> Dict[str, Any]:
        import random
        lid = f"gam_sim_{uuid.uuid4().hex[:10]}"
        logger.info("gam_simulated_line_item", line_item_id=lid)
        return {
            "status": "simulated",
            "platform": "google_ad_manager",
            "line_item_id": lid,
            "targeting_summary": brief_to_gam_targeting(brief, video_meta),
            "note": "Set GAM_ACCESS_TOKEN + GAM_NETWORK_CODE to activate live API",
        }

    def _simulate_stats(self) -> Dict[str, Any]:
        import random
        impressions = random.randint(5000, 50000)
        cpm = round(random.uniform(2.5, 5.5), 2)
        return {
            "status": "simulated",
            "impressions": impressions,
            "clicks": int(impressions * 0.008),
            "revenue_usd": round(impressions / 1000 * cpm, 2),
            "cpm_actual": cpm,
        }


# ─────────────────────────────────────────────────────────────────────────────
# The Trade Desk API calls
# ─────────────────────────────────────────────────────────────────────────────

class TTDService:
    """
    The Trade Desk Bid Manager integration.
    Creates Private Marketplace deals from ZeroClick briefs.
    """

    def __init__(self):
        self.advertiser_id = settings.ttd_advertiser_id
        self.enabled = (
            settings.enable_ttd
            and bool(settings.ttd_api_key and settings.ttd_advertiser_id)
        )
        if not settings.enable_ttd:
            logger.info("ttd_disabled_by_flag")

    async def create_pmp_deal(
        self,
        brief: Dict[str, Any],
        video_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Register a PMP deal with TTD for a specific placement moment."""
        if not self.enabled:
            return self._simulate_deal(brief, video_meta)

        deal_spec = brief_to_ttd_deal(brief, video_meta)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{TTD_BASE}/deal",
                    headers=_ttd_headers(),
                    json=deal_spec,
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    logger.info("ttd_deal_created",
                                deal_id=data.get("DealId"))
                    return {
                        "status": "created",
                        "platform": "the_trade_desk",
                        "deal_id": data.get("DealId"),
                        "floor_cpm": deal_spec["FloorCPM"],
                        "deal_spec": deal_spec,
                    }
                else:
                    logger.error("ttd_deal_failed",
                                 status=resp.status_code, body=resp.text[:200])
        except Exception as e:
            logger.error("ttd_request_error", error=str(e))

        return self._simulate_deal(brief, video_meta)

    async def create_campaign_from_plan(
        self,
        media_plan: Dict[str, Any],
        campaign_brief: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Takes a ranked media plan from Opus and creates TTD ad groups
        for each placement — one ad group per video moment.
        """
        if not self.enabled:
            return self._simulate_campaign(media_plan, campaign_brief)

        results = []
        for placement in media_plan.get("placements", [])[:10]:  # cap at 10
            deal_spec = {
                "DealId": f"viral-intel-{uuid.uuid4().hex[:10]}",
                "Name": f"{campaign_brief.get('advertiser','')} | {placement['video_id']}",
                "FloorCPM": placement.get("estimated_cpm", 3.0) * 0.8,
                "TargetCPM": placement.get("estimated_cpm", 3.0),
                "Targeting": {
                    "PlacementTimestamp": placement.get("timestamp_seconds", 0),
                    "AudienceMatchScore": placement.get("audience_match_score", 0),
                    "VideoId": placement.get("video_id"),
                },
            }
            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    resp = await client.post(
                        f"{TTD_BASE}/deal",
                        headers=_ttd_headers(),
                        json=deal_spec,
                    )
                    results.append({
                        "video_id": placement["video_id"],
                        "deal_id": deal_spec["DealId"],
                        "status": "created" if resp.status_code in (200,201) else "failed",
                    })
            except Exception as e:
                results.append({
                    "video_id": placement["video_id"],
                    "status": "error",
                    "error": str(e),
                })

        return {
            "platform": "the_trade_desk",
            "campaign_name": campaign_brief.get("name", ""),
            "deals_created": len([r for r in results if r["status"] == "created"]),
            "total_placements": len(results),
            "results": results,
        }

    async def get_deal_stats(self, deal_id: str) -> Dict[str, Any]:
        """Pull spend and impression data for a TTD deal."""
        if not self.enabled:
            return self._simulate_stats()

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    f"{TTD_BASE}/deal/{deal_id}/stats",
                    headers=_ttd_headers(),
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.error("ttd_stats_error", error=str(e))

        return self._simulate_stats()

    def _simulate_deal(self, brief, video_meta) -> Dict[str, Any]:
        did = f"ttd_sim_{uuid.uuid4().hex[:10]}"
        logger.info("ttd_simulated_deal", deal_id=did)
        return {
            "status": "simulated",
            "platform": "the_trade_desk",
            "deal_id": did,
            "floor_cpm": float(brief.get("ab.estimated_cpm", 3.0)) * 0.8,
            "deal_spec": brief_to_ttd_deal(brief, video_meta),
            "note": "Set TTD_API_KEY + TTD_ADVERTISER_ID to activate live API",
        }

    def _simulate_campaign(self, media_plan, campaign_brief) -> Dict[str, Any]:
        placements = media_plan.get("placements", [])
        return {
            "status": "simulated",
            "platform": "the_trade_desk",
            "campaign_name": campaign_brief.get("name", ""),
            "deals_created": len(placements),
            "results": [
                {
                    "video_id": p.get("video_id"),
                    "deal_id": f"ttd_sim_{uuid.uuid4().hex[:8]}",
                    "status": "simulated",
                }
                for p in placements
            ],
            "note": "Set TTD_API_KEY + TTD_ADVERTISER_ID to activate live API",
        }

    def _simulate_stats(self) -> Dict[str, Any]:
        import random
        impressions = random.randint(8000, 80000)
        cpm = round(random.uniform(3.0, 6.0), 2)
        return {
            "status": "simulated",
            "impressions": impressions,
            "clicks": int(impressions * 0.01),
            "revenue_usd": round(impressions / 1000 * cpm, 2),
            "win_rate": round(random.uniform(0.3, 0.7), 3),
            "cpm_actual": cpm,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Revenue tracker — writes ad network results back to Neo4j
# ─────────────────────────────────────────────────────────────────────────────

class RevenueTracker:
    """
    Writes deal/line-item stats back to the Neo4j graph.
    Creates (:AdDeal) nodes linked to (:AdvertBrief) and (:Video).
    """

    def __init__(self, db):
        self.db = db

    def upsert_deal(
        self,
        video_id: str,
        platform: str,
        deal_id: str,
        deal_spec: Dict[str, Any],
        stats: Optional[Dict[str, Any]] = None,
    ) -> None:
        cypher = """
        MERGE (d:AdDeal {deal_id: $deal_id})
        SET d += {
            platform: $platform,
            video_id: $video_id,
            floor_cpm: $floor_cpm,
            target_cpm: $target_cpm,
            status: $status,
            impressions: $impressions,
            revenue_usd: $revenue_usd,
            win_rate: $win_rate,
            created_at: timestamp()
        }
        WITH d
        MATCH (v:Video {video_id: $video_id})
        MERGE (v)-[:HAS_DEAL]->(d)
        WITH d
        OPTIONAL MATCH (ab:AdvertBrief {video_id: $video_id})
        FOREACH (_ IN CASE WHEN ab IS NOT NULL THEN [1] ELSE [] END |
            MERGE (ab)-[:ACTIVATED_VIA]->(d)
        )
        """
        s = stats or {}
        self.db.driver.session().run(
            cypher,
            deal_id=deal_id,
            platform=platform,
            video_id=video_id,
            floor_cpm=deal_spec.get("FloorCPM") or deal_spec.get("floor_cpm", 0),
            target_cpm=deal_spec.get("TargetCPM") or deal_spec.get("target_cpm", 0),
            status=s.get("status", "active"),
            impressions=s.get("impressions", 0),
            revenue_usd=s.get("revenue_usd", 0.0),
            win_rate=s.get("win_rate", 0.0),
        )
        logger.info("deal_upserted", deal_id=deal_id, video_id=video_id)

    def get_revenue_summary(self) -> Dict[str, Any]:
        q = """
        MATCH (d:AdDeal)
        RETURN d.platform as platform,
               count(d) as deals,
               sum(d.impressions) as total_impressions,
               sum(d.revenue_usd) as total_revenue,
               avg(d.win_rate) as avg_win_rate
        ORDER BY total_revenue DESC
        """
        with self.db.driver.session() as s:
            recs = s.run(q)
            return {"platforms": [dict(r) for r in recs]}

    def get_deal_list(self, limit: int = 50) -> List[Dict[str, Any]]:
        q = """
        MATCH (v:Video)-[:HAS_DEAL]->(d:AdDeal)
        RETURN v.video_id, v.title, v.category, v.viral_score,
               d.deal_id, d.platform, d.floor_cpm, d.target_cpm,
               d.impressions, d.revenue_usd, d.win_rate, d.status
        ORDER BY d.revenue_usd DESC LIMIT $limit
        """
        with self.db.driver.session() as s:
            recs = s.run(q, limit=limit)
            return [dict(r) for r in recs]


gam_service = GAMService()
ttd_service = TTDService()
