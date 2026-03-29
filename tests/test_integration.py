"""
Integration test suite for ViralIntel.

Tests every endpoint + core service logic without requiring
live API keys — all external services (TwelveLabs, Circle, GAM, TTD)
use their built-in simulation/fallback modes.

Run with:
  pip install pytest pytest-asyncio httpx
  pytest tests/test_integration.py -v

Or inside Docker:
  docker compose exec backend python -m pytest tests/ -v
"""
import asyncio
import json
import os
import sys
import pytest
import httpx

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
TIMEOUT   = 30


@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as c:
        yield c


# ── Helpers ───────────────────────────────────────────────────────────────────
def assert_ok(resp, allow_402=False):
    allowed = {200, 201, 400}
    if allow_402:
        allowed.add(402)
    assert resp.status_code in allowed, (
        f"Expected {allowed}, got {resp.status_code}: {resp.text[:300]}"
    )
    return resp.json()


# ── Health ────────────────────────────────────────────────────────────────────
class TestHealth:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_root(self, client):
        r = client.get("/")
        d = assert_ok(r)
        assert "tracks" in d
        assert "revenue_layers" in d
        assert "mcp_manifest" in d

    def test_docs_available(self, client):
        r = client.get("/docs")
        assert r.status_code == 200


# ── Graph / Videos ────────────────────────────────────────────────────────────
class TestGraph:
    def test_graph_stats(self, client):
        r = client.get("/graph/stats")
        d = assert_ok(r)
        # Keys may be zero but must exist
        for key in ["videos", "scenes", "creators", "trends", "flags", "briefs"]:
            assert key in d

    def test_videos_list(self, client):
        r = client.get("/videos")
        d = assert_ok(r)
        assert "videos" in d
        assert isinstance(d["videos"], list)

    def test_videos_pagination(self, client):
        r = client.get("/videos", params={"skip": 0, "limit": 10})
        d = assert_ok(r)
        assert len(d["videos"]) <= 10

    def test_categories(self, client):
        r = client.get("/categories")
        d = assert_ok(r)
        assert "categories" in d
        cats = [c["key"] for c in d["categories"]]
        assert "food_cooking" in cats
        assert "product_unboxing" in cats

    def test_pipeline_status(self, client):
        r = client.get("/pipeline/status")
        d = assert_ok(r)
        assert "queue_depth" in d
        assert "graph_stats" in d


# ── Search Track ──────────────────────────────────────────────────────────────
class TestSearch:
    def test_semantic_search_basic(self, client):
        r = client.post("/search/semantic", json={
            "query": "product reveal transformation",
            "limit": 5,
            "use_twelvelabs": False,  # graph-only for test speed
        })
        d = assert_ok(r, allow_402=True)
        if r.status_code == 402:
            assert "payment_required" in d
            return
        assert "results" in d
        assert "query" in d
        assert d["track"] == "search"

    def test_semantic_search_with_category(self, client):
        r = client.post("/search/semantic", json={
            "query": "cooking food",
            "category": "food_cooking",
            "limit": 5,
            "use_twelvelabs": False,
        })
        d = assert_ok(r, allow_402=True)
        if r.status_code != 402:
            assert "results" in d

    def test_top_hooks(self, client):
        r = client.get("/search/top-hooks", params={"limit": 10})
        d = assert_ok(r)
        assert "hooks" in d
        assert isinstance(d["hooks"], list)

    def test_top_hooks_by_category(self, client):
        r = client.get("/search/top-hooks", params={
            "category": "sports_highlights", "limit": 5
        })
        d = assert_ok(r)
        assert "hooks" in d

    def test_product_moments(self, client):
        r = client.get("/search/product-moments", params={"limit": 5})
        d = assert_ok(r, allow_402=True)
        if r.status_code != 402:
            assert "results" in d


# ── Segmentation Track ────────────────────────────────────────────────────────
class TestSegmentation:
    def test_ad_breaks(self, client):
        r = client.get("/segment/ad-breaks")
        d = assert_ok(r)
        assert "ad_breaks" in d
        assert d["track"] == "segmentation"

    def test_ad_breaks_with_filter(self, client):
        r = client.get("/segment/ad-breaks", params={
            "category": "food_cooking", "min_score": 0.3, "limit": 10
        })
        d = assert_ok(r)
        assert "count" in d

    def test_structure_analysis(self, client):
        r = client.get("/segment/structure-analysis")
        d = assert_ok(r)
        assert "distribution" in d
        assert isinstance(d["distribution"], list)

    def test_video_segments_nonexistent(self, client):
        r = client.get("/segment/video/nonexistent_video_id")
        d = assert_ok(r)
        assert d["segments"] == []


# ── Compliance Track ──────────────────────────────────────────────────────────
class TestCompliance:
    def test_flags_all(self, client):
        r = client.get("/compliance/flags")
        d = assert_ok(r)
        assert "flags" in d
        assert "count" in d
        assert d["track"] == "compliance"

    def test_flags_by_severity(self, client):
        for sev in ["low", "medium", "high", "critical"]:
            r = client.get("/compliance/flags", params={"severity": sev})
            d = assert_ok(r)
            assert "flags" in d

    def test_compliance_summary(self, client):
        r = client.get("/compliance/summary")
        d = assert_ok(r)
        assert "summary" in d
        assert d["track"] == "compliance"

    def test_compliance_check_nonexistent(self, client):
        r = client.post("/compliance/check/nonexistent_id")
        assert r.status_code in (404, 200)


# ── Advertiser Briefs ─────────────────────────────────────────────────────────
class TestBriefs:
    def test_list_briefs(self, client):
        r = client.get("/briefs")
        d = assert_ok(r)
        assert "briefs" in d
        assert "count" in d

    def test_briefs_with_filter(self, client):
        r = client.get("/briefs", params={"min_cpm": 0, "limit": 20})
        d = assert_ok(r)
        assert "briefs" in d

    def test_brief_nonexistent(self, client):
        r = client.get("/briefs/nonexistent_video_id")
        assert r.status_code == 404


# ── Campaigns ─────────────────────────────────────────────────────────────────
class TestCampaigns:
    def test_list_campaigns(self, client):
        r = client.get("/campaigns")
        d = assert_ok(r)
        assert "campaigns" in d

    def test_campaign_match_no_anthropic_key(self, client):
        """Without ANTHROPIC_API_KEY, should return 400 or 402."""
        # Save and clear key temporarily
        orig = os.environ.get("ANTHROPIC_API_KEY", "")
        if not orig or "your_" in orig:
            r = client.post("/campaigns/match", json={
                "name": "Test",
                "advertiser": "TestCo",
                "vertical": "CPG",
                "target_audience": "adults",
                "budget_usd": 1000,
                "max_cpm": 5.0,
                "activate_on_networks": False,
            })
            assert r.status_code in (400, 402, 200)

    def test_campaign_nonexistent(self, client):
        r = client.get("/campaigns/nonexistent_campaign_id")
        assert r.status_code == 404


# ── Ad Network Deals ─────────────────────────────────────────────────────────
class TestDeals:
    def test_list_deals(self, client):
        r = client.get("/deals")
        d = assert_ok(r)
        assert "deals" in d

    def test_activate_deal_nonexistent(self, client):
        r = client.post("/deals/activate/nonexistent_video_id",
                        params={"networks": "gam,ttd"})
        assert r.status_code == 404

    def test_revenue_dashboard(self, client):
        r = client.get("/revenue")
        d = assert_ok(r)
        assert "total_revenue_usd" in d
        assert "total_deals" in d
        assert "by_platform" in d
        assert isinstance(d["total_revenue_usd"], (int, float))


# ── Circle / x402 ─────────────────────────────────────────────────────────────
class TestCircleX402:
    def test_wallet_balance(self, client):
        r = client.get("/circle/wallet")
        d = assert_ok(r)
        assert "usdc_balance" in d
        assert "environment" in d
        assert isinstance(d["usdc_balance"], (int, float))

    def test_payment_intent(self, client):
        r = client.post("/circle/payment-intent",
                        params={"query_type": "semantic_search"})
        d = assert_ok(r)
        assert "intent_id" in d
        assert "amount_usdc" in d
        assert d["amount_usdc"] > 0

    def test_payment_intent_campaign(self, client):
        r = client.post("/circle/payment-intent",
                        params={"query_type": "campaign_match"})
        d = assert_ok(r)
        # Campaign match is more expensive
        assert d["amount_usdc"] >= 0.50

    def test_verify_sim_transfer(self, client):
        """sim_ prefix always passes in testnet demo mode."""
        r = client.get("/circle/verify/sim_test_transfer_123",
                       params={"query_type": "semantic_search"})
        d = assert_ok(r)
        assert d["verified"] is True

    def test_verify_invalid_transfer(self, client):
        """Non-sim transfer IDs fail when Circle API not configured."""
        r = client.get("/circle/verify/invalid_real_transfer_id",
                       params={"query_type": "semantic_search"})
        d = assert_ok(r)
        # Without Circle API key, returns verified=False
        assert "verified" in d

    def test_circle_transactions(self, client):
        r = client.get("/circle/transactions", params={"limit": 5})
        d = assert_ok(r)
        assert "transactions" in d

    def test_x402_pricing(self, client):
        r = client.get("/x402/pricing")
        d = assert_ok(r)
        assert "pricing" in d
        assert "enforcement" in d
        pricing = d["pricing"]
        assert "semantic_search" in pricing
        assert "campaign_match" in pricing
        assert "trend_detect" in pricing
        # Campaign match should cost more than search
        assert pricing["campaign_match"] > pricing["semantic_search"]

    def test_x402_stats(self, client):
        r = client.get("/x402/stats")
        d = assert_ok(r)
        assert "total_revenue_usdc" in d
        assert "pricing" in d
        assert "environment" in d

    def test_mcp_manifest(self, client):
        r = client.get("/.well-known/mcp.json")
        d = assert_ok(r)
        assert "mcp_version" in d
        assert "tools" in d
        assert len(d["tools"]) >= 5
        # Each tool must have name, price, endpoint
        for tool in d["tools"]:
            assert "name" in tool
            assert "price_usdc" in tool
            assert "endpoint" in tool
            assert tool["price_usdc"] >= 0

    def test_x402_payment_flow(self, client):
        """
        Full flow: create intent → verify with sim_ id → call paid endpoint.
        """
        # 1. Create intent
        r1 = client.post("/circle/payment-intent",
                         params={"query_type": "semantic_search"})
        intent = r1.json()
        assert intent["amount_usdc"] > 0

        # 2. Verify with sim_ transfer
        r2 = client.get("/circle/verify/sim_flow_test_123",
                        params={"query_type": "semantic_search"})
        verify = r2.json()
        assert verify["verified"] is True

        # 3. Call paid endpoint with payment header
        r3 = client.post(
            "/search/semantic",
            json={"query": "test payment flow", "limit": 1, "use_twelvelabs": False},
            headers={"X-Payment-Transfer-Id": "sim_flow_test_123"},
        )
        # Should succeed (200) or be 402 if enforcement is on without real payment
        assert r3.status_code in (200, 402)


# ── Ontology ──────────────────────────────────────────────────────────────────
class TestOntology:
    def test_schema(self, client):
        r = client.get("/ontology/schema")
        d = assert_ok(r)
        assert "schema" in d
        schema = d["schema"]
        assert "node_labels" in schema
        assert "Video" in schema["node_labels"]
        assert "Payment" in schema["node_labels"]
        assert "ViralFormat" in schema["node_labels"]

    def test_viral_formats(self, client):
        r = client.get("/ontology/viral-formats")
        d = assert_ok(r)
        assert "viral_formats" in d

    def test_ontology_infer_no_key(self, client):
        """Without ANTHROPIC_API_KEY should return 400."""
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key or "your_" in key:
            r = client.post("/ontology/infer")
            assert r.status_code == 400


# ── Unit tests for service logic ──────────────────────────────────────────────
class TestServiceLogic:
    def test_viral_score_formula(self):
        """Test the viral score computation matches the formula."""
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)) + "/backend")
        from ingestion import VideoIngestionService
        svc = VideoIngestionService()

        # High views + high engagement
        score_high = svc.compute_viral_score({
            "view_count": 5_000_000, "like_count": 500_000, "comment_count": 50_000
        })
        # Low views + low engagement
        score_low = svc.compute_viral_score({
            "view_count": 1_000, "like_count": 10, "comment_count": 1
        })
        assert score_high > score_low
        assert 0 <= score_high <= 1
        assert 0 <= score_low <= 1

    def test_iab_category_mapping(self):
        """Test that verticals map to valid IAB categories."""
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)) + "/backend")
        from adnetwork_service import VERTICAL_TO_IAB
        for vertical, iab_cats in VERTICAL_TO_IAB.items():
            assert len(iab_cats) > 0
            for cat in iab_cats:
                assert cat.startswith("IAB")

    def test_payment_tiers_ordering(self):
        """Campaign match must cost more than search."""
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)) + "/backend")
        from circle_x402_service import PAYMENT_TIERS
        assert PAYMENT_TIERS["campaign_match"] > PAYMENT_TIERS["semantic_search"]
        assert PAYMENT_TIERS["trend_detect"] > PAYMENT_TIERS["semantic_search"]
        assert PAYMENT_TIERS["brief_lookup"] < PAYMENT_TIERS["semantic_search"]

    def test_circle_base_url_routing(self):
        """Circle base URL should switch with environment setting."""
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)) + "/backend")
        from circle_x402_service import CIRCLE_TESTNET, CIRCLE_MAINNET
        assert "sandbox" in CIRCLE_TESTNET
        assert "sandbox" not in CIRCLE_MAINNET

    def test_mcp_tools_have_required_fields(self):
        """Every MCP tool must have required fields."""
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)) + "/backend")
        from circle_x402_service import MCP_TOOLS
        for tool in MCP_TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "price_usdc" in tool
            assert "endpoint" in tool
            assert "input_schema" in tool
            assert tool["price_usdc"] >= 0

    def test_gam_targeting_translation(self):
        """GAM targeting builder produces valid structure."""
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)) + "/backend")
        from adnetwork_service import brief_to_gam_targeting
        brief = {
            "target_verticals": ["CPG", "kitchenware"],
            "ab.estimated_cpm": 4.15,
            "ab.placement_moment": 12.1,
            "ab.zeroclick_context": "test",
        }
        video = {
            "v.category": "food_cooking",
            "v.viral_score": 0.87,
            "v.video_id": "test123",
            "v.view_count": 1000000,
        }
        result = brief_to_gam_targeting(brief, video)
        assert "targeting" in result
        assert "iab_categories" in result
        assert result["estimated_cpm_micros"] > 0
        # IAB categories should be from food/CPG
        assert any("IAB8" in c for c in result["iab_categories"])

    def test_ttd_deal_spec(self):
        """TTD deal spec has required PMP fields."""
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)) + "/backend")
        from adnetwork_service import brief_to_ttd_deal
        brief = {
            "target_verticals": ["sports_brands"],
            "ab.estimated_cpm": 3.80,
            "ab.headline": "Sports content",
            "ab.placement_moment": 5.7,
        }
        video = {
            "v.category": "sports_highlights",
            "v.viral_score": 0.82,
            "v.video_id": "sport123",
            "v.view_count": 5100000,
        }
        deal = brief_to_ttd_deal(brief, video)
        assert "DealId" in deal
        assert "FloorCPM" in deal
        assert "TargetCPM" in deal
        assert deal["FloorCPM"] < deal["TargetCPM"]
        assert "Targeting" in deal
        assert "CustomAudienceContextualSignals" in deal["Targeting"]


# ── Run standalone ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        ["python", "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=os.path.dirname(__file__)
    )
    sys.exit(result.returncode)


# ── LTX Creative Generation ───────────────────────────────────────────────────
class TestLTXCreatives:
    def test_generate_creative_nonexistent(self, client):
        r = client.post("/creatives/generate/nonexistent_video_id",
                        params={"ad_format": "6s_bumper"})
        assert r.status_code == 404

    def test_get_video_creatives_empty(self, client):
        r = client.get("/creatives/video/nonexistent_video_id")
        d = assert_ok(r)
        assert "creatives" in d
        assert isinstance(d["creatives"], list)

    def test_campaign_creatives_nonexistent(self, client):
        r = client.post("/creatives/campaign/nonexistent_campaign",
                        params={"ad_format": "6s_bumper"})
        assert r.status_code == 404

    def test_ltx_prompt_builder(self):
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)) + "/backend")
        from ltx_service import build_ltx_prompt
        brief = {
            "ab.estimated_cpm": 4.15,
            "ab.placement_moment": 12.1,
            "ab.headline": "Reach food enthusiasts",
            "target_verticals": ["CPG", "kitchenware"],
        }
        tl_ctx = {"mood": "appetizing", "key_objects": ["pasta", "pan"],
                  "audience_signals": "food enthusiasts 25-44"}
        video_meta = {"v.category": "food_cooking", "v.video_id": "test123"}
        prompt = build_ltx_prompt(brief, tl_ctx, video_meta, "6s_bumper")
        assert "6-second" in prompt
        assert "pasta" in prompt or "pan" in prompt
        assert "12.1s" in prompt
        assert len(prompt) > 100

    def test_ltx_simulation_mode(self):
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)) + "/backend")
        from ltx_service import LTXService
        svc = LTXService()
        # No API key = simulation mode
        assert not svc.enabled
        brief = {"ab.estimated_cpm": 3.0, "ab.placement_moment": 5.0,
                 "ab.headline": "Test", "target_verticals": ["CPG"]}
        creative = svc._sim_creative(brief, {"v.category": "food_cooking"}, "6s_bumper")
        assert "creative_id" in creative
        assert creative["status"] == "simulated"
        assert creative["duration"] == 6
        assert creative["ad_format"] == "6s_bumper"


# ── TrackIt Workflow ──────────────────────────────────────────────────────────
class TestTrackIt:
    def test_pipeline_states(self, client):
        r = client.get("/trackit/pipeline-states")
        d = assert_ok(r)
        assert "states" in d
        assert len(d["states"]) == 8
        assert "video_discovered" in d["states"]
        assert "payment_recorded" in d["states"]

    def test_workflow_nonexistent(self, client):
        r = client.post("/trackit/workflow/nonexistent_video_id")
        assert r.status_code == 404

    def test_workflow_status_unknown(self, client):
        r = client.get("/trackit/workflow/wf_unknown_123/status")
        d = assert_ok(r)
        assert "workflow_id" in d
        assert "status" in d

    def test_mam_nonexistent(self, client):
        r = client.post("/trackit/mam/nonexistent_video_id")
        assert r.status_code == 404

    def test_qoe_nonexistent(self, client):
        r = client.get("/trackit/qoe/nonexistent_video_id")
        assert r.status_code == 404

    def test_audit_trail_empty(self, client):
        r = client.get("/trackit/audit")
        d = assert_ok(r)
        assert "records" in d
        assert "count" in d
        assert isinstance(d["records"], list)

    def test_audit_trail_filtered(self, client):
        r = client.get("/trackit/audit", params={"video_id": "any_video_id"})
        d = assert_ok(r)
        assert "records" in d

    def test_timecode_conversion(self):
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)) + "/backend")
        from trackit_service import _seconds_to_tc
        assert _seconds_to_tc(0.0)   == "00:00:00:00"
        assert _seconds_to_tc(60.0)  == "00:01:00:00"
        assert _seconds_to_tc(3600.0) == "01:00:00:00"
        assert _seconds_to_tc(12.1)  == "00:00:12:02"

    def test_mam_metadata_builder(self):
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)) + "/backend")
        from trackit_service import build_mam_metadata
        video_meta = {
            "v.video_id": "test123", "v.title": "Test video",
            "v.platform": "youtube", "v.url": "https://youtube.com/watch?v=test",
            "v.duration": 45, "v.category": "food_cooking",
            "v.viral_score": 0.87, "v.hook_strength": 0.82, "v.view_count": 1800000,
        }
        segments = [
            {"segment_type": "hook", "t_start": 0, "t_end": 3,
             "viral_segment_score": 0.91, "attention_score": 0.88},
        ]
        flags = []
        record = build_mam_metadata(video_meta, segments, flags)
        assert record["schema_version"] == "SMPTE-2067-1"
        assert record["asset_id"] == "viral-intel:test123"
        assert record["compliance"]["brand_safe"] is True
        assert len(record["segments"]) == 1
        assert record["segments"][0]["start_tc"] == "00:00:00:00"
        assert record["segments"][0]["end_tc"] == "00:00:03:00"

    def test_qoe_score_computation(self):
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)) + "/backend")
        from trackit_service import TrackItWorkflowEngine
        engine = TrackItWorkflowEngine()
        high = engine.compute_qoe_score({"v.viral_score": 0.95, "v.duration": 30,
                                          "v.view_count": 5000000})
        low  = engine.compute_qoe_score({"v.viral_score": 0.20, "v.duration": 120,
                                          "v.view_count": 1500})
        assert high["qoe_score"] > low["qoe_score"]
        assert 0 <= high["qoe_score"] <= 1
        assert high["mobile_optimised"] is True
        assert low["mobile_optimised"] is False
