"""
FastAPI backend: REST API for all three tracks + graph stats + pipeline control.
"""
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import uuid
import redis
from rq import Queue
from rq.job import Job, NoSuchJobError

from config import settings, VIDEO_CATEGORIES
from database import db
from twelvelabs_service import tl_service
from zeroclick_service import zeroclick_service
from opus_service import infer_ontology, match_campaign_to_inventory, detect_trends
from adnetwork_service import gam_service, ttd_service, RevenueTracker
from circle_x402_service import (
    circle_service, CircleWalletService, X402PaymentGate,
    MCP_TOOLS, PAYMENT_TIERS
)
from ltx_service import ltx_service, build_ltx_prompt
from trackit_service import trackit_engine, build_mam_metadata, PIPELINE_STATES
import structlog

logger = structlog.get_logger()
revenue_tracker = RevenueTracker(db)
x402_gate = X402PaymentGate(circle_service, db)

app = FastAPI(
    title="Viral Video Intelligence API",
    description="TwelveLabs + Neo4j + ZeroClick.ai — NAB 2026 Hackathon",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

redis_conn = redis.from_url(settings.redis_url)
pipeline_queue = Queue("pipeline", connection=redis_conn)
ingest_queue = Queue("ingest", connection=redis_conn)


@app.on_event("startup")
async def startup():
    try:
        db.init_schema()
        logger.info("startup_complete")
    except Exception as e:
        logger.error("startup_error", error=str(e))

    # TwelveLabs index init — non-fatal, retried on first use
    try:
        await tl_service.get_or_create_index()
        logger.info("tl_index_ready")
    except Exception as e:
        logger.warning("tl_index_init_deferred", error=str(e)[:120])


# ── Pipeline Control ──────────────────────────────────────────────────────────

@app.post("/pipeline/start")
async def start_pipeline():
    """Kick off full 500-video ingestion pipeline."""
    from worker import run_full_ingestion
    job = ingest_queue.enqueue(run_full_ingestion, job_timeout=7200)
    return {"job_id": job.id, "status": "queued",
            "message": "Full ingestion pipeline started. Monitor via /pipeline/status"}


@app.get("/pipeline/status")
async def pipeline_status():
    """Get queue depths and recent job counts."""
    pipeline_jobs = len(pipeline_queue)
    ingest_jobs = len(ingest_queue)
    failed = pipeline_queue.failed_job_registry
    finished = pipeline_queue.finished_job_registry
    stats = db.get_graph_stats()
    return {
        "queue_depth": pipeline_jobs + ingest_jobs,
        "failed_jobs": len(failed),
        "completed_jobs": len(finished),
        "graph_stats": stats,
    }


@app.get("/pipeline/job/{job_id}")
async def get_job(job_id: str):
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        return {"id": job.id, "status": job.get_status(), "result": job.result}
    except NoSuchJobError:
        raise HTTPException(status_code=404, detail="Job not found")


# ── Graph & Videos ────────────────────────────────────────────────────────────

@app.get("/graph/stats")
async def graph_stats():
    return db.get_graph_stats()


@app.get("/videos")
async def list_videos(
    skip: int = 0,
    limit: int = 50,
    category: Optional[str] = None,
):
    videos = db.get_videos_paginated(skip=skip, limit=limit, category=category)
    INDEX_ID = "69c88c3e74e8033fe643df3b"
    TL_MAP = {"local_news_ABC_World_News_Tonight_with_David_Muir_F":"69c8ad9e9639891c46130524","local_news_NBC_Nightly_News_Full_Episode_-_Mar_21":"69c8adf611890571f37bca05","local_news_NBC_Nightly_News_Full_Episode_-_March_7":"69c8ae45c704e7c92b859857","local_prod_4K_Forest_-_Cinematic_Forest_-_4K_Nature":"69c8ae9274e8033fe643ead9","local_prod_A_THUNDERBIRDS_REUNION_Behind_the_Scenes":"69c8aeb811890571f37bca3f","local_prod_Bald_Eagles_on_the_Nooksack_River__Washi":"69c8af3911890571f37bca52","local_prod_What_14_Movies_Looked_Like_Behind_The_Sc":"69c8af6611890571f37bca61","local_spor_wilt_59min":"69c8afeb5905babfd4fc49d8"}
    for v in videos:
        vid = v.get("v.video_id","")
        if not v.get("v.url") and vid in TL_MAP:
            v["v.url"] = f"https://playground.twelvelabs.io/indexes/{INDEX_ID}/videos/{TL_MAP[vid]}"
            v["v.platform"] = "twelvelabs"
    return {"videos": videos}


@app.get("/videos/{video_id}/similar")
async def similar_videos(video_id: str, limit: int = 10):
    return {"similar": db.find_similar_videos(video_id, limit)}


@app.get("/categories")
async def list_categories():
    return {
        "categories": [
            {"key": k, "description": v["description"],
             "target_count": v["count"], "verticals": v["advertiser_verticals"]}
            for k, v in VIDEO_CATEGORIES.items()
        ]
    }


# ── Search Track ──────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    min_viral_score: float = 0.3
    limit: int = 20
    use_twelvelabs: bool = True


class ArchiveSearchRequest(BaseModel):
    query: str
    content_type: str = "any"   # sports | news | production | any
    limit: int = 20
    time_savings_baseline_hours: float = 8.0  # for ROI calculation


@app.post("/search/semantic")
async def semantic_search(req: SearchRequest, request: Request):
    """
    Archive Search Track: semantic moment discovery using TwelveLabs Marengo.
    Routes through AWS Bedrock if credentials set, falls back to direct API.
    Requires x402 USDC micropayment when X402_ENFORCE_PAYMENT=true.
    """
    gate_resp = await x402_gate.gate(request, "semantic_search")
    if gate_resp:
        return gate_resp
    results = []

    if req.use_twelvelabs:
        tl_results = await tl_service.semantic_search(req.query, limit=req.limit)
        for r in tl_results:
            tl_vid_id = r.get("tl_video_id")
            with db.driver.session() as s:
                rec = s.run(
                    """MATCH (v:Video {twelvelabs_video_id: $tid})
                       OPTIONAL MATCH (v)-[:HAS_BRIEF]->(ab:AdvertBrief)
                       RETURN v.video_id, v.title, v.url, v.category,
                              v.viral_score, v.view_count, ab.headline as brief""",
                    tid=tl_vid_id
                ).single()
                if rec:
                    results.append({**r, **dict(rec)})
                else:
                    results.append(r)
    else:
        results = db.search_by_semantic_label(
            req.query, req.category, req.min_viral_score, req.limit
        )

    return {
        "query":   req.query,
        "count":   len(results),
        "results": results,
        "track":   "search",
        "mode":    tl_service.get_mode_info(),
    }


@app.post("/search/archive")
async def archive_search(req: ArchiveSearchRequest, request: Request):
    """
    Archive-optimised search for broadcast/sports/news professionals.
    Returns timestamped results with time-savings ROI calculation.
    Example: 'sunset over water with birds flying', content_type='production'
    """
    gate_resp = await x402_gate.gate(request, "semantic_search")
    if gate_resp:
        return gate_resp

    results = await tl_service.search_archive_moment(
        req.query, req.content_type, req.limit
    )

    # Enrich with Neo4j metadata
    enriched = []
    for r in results:
        tl_vid_id = r.get("tl_video_id")
        with db.driver.session() as s:
            rec = s.run(
                """MATCH (v:Video {twelvelabs_video_id: $tid})
                   RETURN v.video_id, v.title, v.url, v.category,
                          v.viral_score, v.view_count, v.duration""",
                tid=tl_vid_id
            ).single()
            enriched.append({**r, **(dict(rec) if rec else {})})

    # ROI calculation
    search_time_minutes = round(len(results) * 0.04, 1)  # ~2.4 sec per result
    baseline_hours = req.time_savings_baseline_hours
    time_saved = round(baseline_hours - (search_time_minutes / 60), 2)
    cost_saved  = round(time_saved * 75, 0)  # $75/hr FTE cost

    return {
        "query":        req.query,
        "content_type": req.content_type,
        "count":        len(enriched),
        "results":      enriched,
        "roi": {
            "search_time_minutes":   search_time_minutes,
            "baseline_hours":        baseline_hours,
            "time_saved_hours":      time_saved,
            "estimated_cost_saved":  f"${cost_saved:.0f}",
            "cost_per_query":        "$0.05 USDC",
        },
        "mode": tl_service.get_mode_info(),
        "track": "archive_search",
    }


@app.get("/search/similar/{tl_video_id}")
async def find_similar(tl_video_id: str, limit: int = 10):
    """Find clips visually similar to a specific moment — 'find more like this'."""
    results = await tl_service.find_similar_moments(tl_video_id, limit=limit)
    return {"source_id": tl_video_id, "similar": results, "count": len(results)}


@app.get("/search/bedrock-status")
async def bedrock_status():
    """Show whether Bedrock or direct API is active."""
    return tl_service.get_mode_info()



@app.get("/search/top-hooks")
async def top_hook_moments(
    category: Optional[str] = None,
    limit: int = 20,
):
    """Return top Hook segments ranked by viral_segment_score."""
    return {
        "hooks": db.search_top_hook_moments(category, limit),
        "track": "search",
    }


@app.get("/search/product-moments")
async def product_moments(limit: int = 20):
    """Find product reveal moments across all videos."""
    return await semantic_search(SearchRequest(
        query="product reveal visible close up",
        limit=limit,
        use_twelvelabs=True,
    ))


# ── Segmentation Track ────────────────────────────────────────────────────────

@app.get("/segment/video/{video_id}")
async def get_video_segments(video_id: str, format: str = "json"):
    """Return all scene segments for a video. format=json|xml|edl"""
    with db.driver.session() as s:
        recs = s.run(
            """MATCH (sc:Scene)-[:SEGMENT_OF]->(v:Video {video_id: $vid})
               RETURN sc.scene_id, sc.t_start, sc.t_end, sc.segment_type,
                      sc.label, sc.viral_segment_score, sc.attention_score,
                      sc.description, sc.confidence, sc.is_ad_break_candidate,
                      sc.boundary_quality, sc.content_type
               ORDER BY sc.t_start""",
            vid=video_id
        )
        segments = [dict(r) for r in recs]

    if format == "xml":
        xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                     f'<segmentation video_id="{video_id}" count="{len(segments)}">']
        for s in segments:
            xml_lines.append(
                f'  <segment type="{s.get("sc.segment_type","")}" '
                f'start="{s.get("sc.t_start",0)}" end="{s.get("sc.t_end",0)}" '
                f'confidence="{s.get("sc.confidence",0)}" '
                f'ad_break="{s.get("sc.is_ad_break_candidate",False)}">'
                f'<label>{s.get("sc.label","")}</label>'
                f'<description>{s.get("sc.description","")}</description>'
                f'</segment>'
            )
        xml_lines.append('</segmentation>')
        from fastapi.responses import Response
        return Response(content="\n".join(xml_lines), media_type="application/xml")

    if format == "edl":
        lines = [f"TITLE: {video_id}", "FCM: NON-DROP FRAME", ""]
        for i, s in enumerate(segments, 1):
            t_s = s.get("sc.t_start", 0)
            t_e = s.get("sc.t_end", 0)
            def to_tc(sec):
                h = int(sec//3600); m = int((sec%3600)//60)
                s2 = int(sec%60); f = int((sec%1)*25)
                return f"{h:02d}:{m:02d}:{s2:02d}:{f:02d}"
            lines.append(f"{i:03d}  AX       V     C        {to_tc(t_s)} {to_tc(t_e)} {to_tc(t_s)} {to_tc(t_e)}")
            lines.append(f"* FROM CLIP NAME: {s.get('sc.label','segment')}")
            lines.append("")
        from fastapi.responses import Response
        return Response(content="\n".join(lines), media_type="text/plain")

    return {"video_id": video_id, "segments": segments,
            "count": len(segments), "track": "segmentation"}


@app.post("/segment/analyze/{video_id}")
async def analyze_video_segmentation(
    video_id: str,
    content_type: str = "auto",
):
    """
    On-demand segmentation of a video using TwelveLabs Marengo + Pegasus.
    content_type: sports | news | studio | documentary | auto
    Returns segments with full structural analysis.
    """
    with db.driver.session() as s:
        rec = s.run(
            "MATCH (v:Video {video_id: $vid}) RETURN v.twelvelabs_video_id as tl_id",
            vid=video_id
        ).single()
    if not rec or not rec["tl_id"]:
        raise HTTPException(404, "Video not indexed in TwelveLabs yet")

    # Check Neo4j first for existing segments
    with db.driver.session() as s:
        existing = s.run("""
            MATCH (v:Video {video_id: $vid})-[:HAS_SCENE]->(sc:Scene)
            RETURN sc ORDER BY sc.t_start
        """, vid=video_id).data()
    
    if existing:
        segments = [{"sc."+k: v for k, v in dict(r["sc"]).items()} for r in existing]
        segments = [dict(r["sc"]) for r in existing]
    else:
        segments = await tl_service.segment_video(rec["tl_id"], content_type=content_type)

    # Write segments back to Neo4j
    for i, seg in enumerate(segments):
        scene_id = f"{video_id}_seg_{i:03d}"
        with db.driver.session() as s:
            s.run("""
                MERGE (sc:Scene {scene_id: $sid})
                SET sc.video_id = $vid,
                    sc.t_start = $t_start, sc.t_end = $t_end,
                    sc.segment_type = $stype, sc.label = $label,
                    sc.description = $desc, sc.confidence = $conf,
                    sc.viral_segment_score = $score,
                    sc.attention_score = $attn,
                    sc.is_ad_break_candidate = $ad_break,
                    sc.boundary_quality = $bq,
                    sc.content_type = $ct
                MERGE (v:Video {video_id: $vid})
                MERGE (sc)-[:SEGMENT_OF]->(v)
            """,
                sid=scene_id, vid=video_id,
                t_start=float(seg.get("t_start", 0)),
                t_end=float(seg.get("t_end", 0)),
                stype=seg.get("segment_type", "chapter"),
                label=seg.get("label", ""),
                desc=seg.get("description", ""),
                conf=float(seg.get("confidence", 0.8)),
                score=float(seg.get("viral_segment_score", 0.5)),
                attn=float(seg.get("attention_score", 0.5)),
                ad_break=bool(seg.get("is_ad_break_candidate", False)),
                bq=seg.get("boundary_quality", "soft"),
                ct=seg.get("content_type", content_type),
            )

    ad_breaks = [s for s in segments if s.get("is_ad_break_candidate")]
    return {
        "video_id":    video_id,
        "content_type": content_type,
        "segments":    segments,
        "count":       len(segments),
        "ad_breaks":   ad_breaks,
        "ad_break_count": len(ad_breaks),
        "track": "segmentation",
    }


@app.get("/segment/ad-breaks")
async def find_ad_break_moments(
    category: Optional[str] = None,
    content_type: Optional[str] = None,
    min_score: float = 0.5,
    limit: int = 30,
):
    """Find optimal ad-break insertion points across the corpus."""
    q = """
    MATCH (sc:Scene)-[:SEGMENT_OF|HAS_SCENE]-(v:Video)
    WHERE (sc.segment_type = 'ad_break_point'
           OR sc.segment_type = 'commercial_break_point'
           OR sc.is_ad_break_candidate = true)
      AND sc.viral_segment_score >= $min_score
    """
    if category:
        q += " AND v.category = $category"
    if content_type:
        q += " AND sc.content_type = $content_type"
    q += """
    RETURN v.video_id, v.title, v.url, v.category, v.viral_score,
           sc.t_start, sc.t_end, sc.viral_segment_score, sc.label,
           sc.boundary_quality, sc.confidence, sc.content_type
    ORDER BY sc.viral_segment_score DESC LIMIT $limit
    """
    with db.driver.session() as s:
        recs = s.run(q, min_score=min_score, category=category,
                     content_type=content_type, limit=limit)
        results = [dict(r) for r in recs]
    return {"ad_breaks": results, "count": len(results), "track": "segmentation"}


@app.get("/segment/ad-breaks/optimize/{video_id}")
async def optimize_ad_breaks(
    video_id: str,
    n_breaks: int = 5,
    min_gap_seconds: float = 300.0,
):
    """
    Return the optimal N ad-break positions for a video.
    Respects minimum gap between breaks (default 5 minutes).
    Scores breaks by: confidence + boundary_quality + attention dip.
    """
    with db.driver.session() as s:
        recs = s.run(
            """MATCH (sc:Scene)-[:SEGMENT_OF]->(v:Video {video_id: $vid})
               WHERE sc.is_ad_break_candidate = true OR
                     sc.segment_type IN ['commercial_break_point','ad_break_point','transition']
               RETURN sc.t_start, sc.t_end, sc.label, sc.viral_segment_score,
                      sc.confidence, sc.boundary_quality, sc.segment_type
               ORDER BY sc.viral_segment_score DESC""",
            vid=video_id
        )
        candidates = [dict(r) for r in recs]

    # Greedy selection with minimum gap constraint
    selected = []
    for c in candidates:
        t = c.get("sc.t_start", 0)
        if all(abs(t - s["sc.t_start"]) >= min_gap_seconds for s in selected):
            selected.append(c)
        if len(selected) >= n_breaks:
            break

    selected.sort(key=lambda x: x.get("sc.t_start", 0))
    return {
        "video_id":     video_id,
        "n_requested":  n_breaks,
        "n_found":      len(selected),
        "min_gap_s":    min_gap_seconds,
        "ad_breaks":    selected,
        "track": "segmentation",
    }


@app.get("/segment/story-boundaries/{video_id}")
async def get_story_boundaries(video_id: str):
    """
    Return story boundary segments — where new topics/stories begin.
    Used for news segmentation and documentary chapter detection.
    """
    with db.driver.session() as s:
        recs = s.run(
            """MATCH (sc:Scene)-[:SEGMENT_OF]->(v:Video {video_id: $vid})
               WHERE sc.is_story_boundary = true OR
                     sc.segment_type IN ['story_intro','story_boundary','chapter',
                                         'cold_open','act_1','act_2','act_3','act_4']
               RETURN sc.t_start, sc.t_end, sc.label, sc.description,
                      sc.segment_type, sc.confidence, sc.topic
               ORDER BY sc.t_start""",
            vid=video_id
        )
        boundaries = [dict(r) for r in recs]
    return {"video_id": video_id, "story_boundaries": boundaries,
            "count": len(boundaries), "track": "segmentation"}


@app.get("/segment/export/{video_id}")
async def export_segments(video_id: str, format: str = "json"):
    """
    Export segmentation data in production formats.
    format: json | xml | edl | csv
    JSON output: {start, end, type, confidence, description, is_ad_break}
    """
    with db.driver.session() as s:
        recs = s.run(
            """MATCH (sc:Scene)-[:SEGMENT_OF]->(v:Video {video_id: $vid})
               RETURN sc.t_start as start, sc.t_end as end,
                      sc.segment_type as type, sc.confidence as confidence,
                      sc.label as label, sc.description as description,
                      sc.viral_segment_score as score,
                      sc.is_ad_break_candidate as is_ad_break,
                      sc.boundary_quality as boundary_quality,
                      sc.content_type as content_type
               ORDER BY sc.t_start""",
            vid=video_id
        )
        segs = [dict(r) for r in recs]

    if format == "csv":
        lines = ["start,end,type,confidence,label,is_ad_break,score"]
        for s in segs:
            lines.append(
                f"{s.get('start',0)},{s.get('end',0)},{s.get('type','')},"
                f"{s.get('confidence',0)},\"{s.get('label','')}\","
                f"{s.get('is_ad_break',False)},{s.get('score',0)}"
            )
        from fastapi.responses import Response
        return Response(content="\n".join(lines), media_type="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={video_id}_segments.csv"})

    if format == "xml":
        ad_ct = sum(1 for s in segs if s.get("is_ad_break"))
        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<segmentation video_id="{video_id}" segment_count="{len(segs)}" ad_break_count="{ad_ct}">',
        ]
        for s in segs:
            xml_lines.append(
                f'  <segment type="{s.get("type","")}" '
                f'start="{s.get("start",0):.3f}" '
                f'end="{s.get("end",0):.3f}" '
                f'confidence="{s.get("confidence",0):.3f}" '
                f'is_ad_break="{str(s.get("is_ad_break",False)).lower()}" '
                f'boundary_quality="{s.get("boundary_quality","soft")}">'
                f'<label><![CDATA[{s.get("label","")}]]></label>'
                f'<description><![CDATA[{s.get("description","")}]]></description>'
                f'</segment>'
            )
        xml_lines.append('</segmentation>')
        from fastapi.responses import Response
        return Response(
            content="\n".join(xml_lines),
            media_type="application/xml",
            headers={"Content-Disposition": f"attachment; filename={video_id}_segments.xml"}
        )

    # Default JSON — matches challenge spec: {start, end, type, confidence, description}
    return {
        "video_id":        video_id,
        "segment_count":   len(segs),
        "ad_break_count":  sum(1 for s in segs if s.get("is_ad_break")),
        "segments":        segs,
        "track":           "segmentation",
        "export_format":   "json",
    }


@app.get("/segment/structure-analysis")
async def structure_analysis(category: Optional[str] = None):
    """Aggregate segment type distribution across the corpus."""
    q = "MATCH (sc:Scene)-[:SEGMENT_OF|HAS_SCENE]-(v:Video)"
    if category:
        q += " WHERE v.category = $category"
    q += """
    RETURN sc.segment_type as type,
           count(*) as count,
           avg(sc.viral_segment_score) as avg_viral_score,
           avg(sc.attention_score) as avg_attention,
           sum(CASE WHEN sc.is_ad_break_candidate THEN 1 ELSE 0 END) as ad_break_count
    ORDER BY count DESC
    """
    with db.driver.session() as s:
        recs = s.run(q, category=category)
        distribution = [dict(r) for r in recs]
    return {"distribution": distribution, "category": category, "track": "segmentation"}



# ── Compliance Track ──────────────────────────────────────────────────────────

@app.get("/compliance/flags")
async def compliance_flags(
    severity: Optional[str] = None,
    category: Optional[str] = None,
):
    """Return all compliance flags, optionally filtered by severity."""
    flags = db.get_compliance_flags(severity)
    if category:
        flags = [f for f in flags if f.get("v.category") == category]
    return {
        "flags": flags,
        "count": len(flags),
        "track": "compliance",
    }


@app.get("/compliance/summary")
async def compliance_summary():
    """Aggregate compliance violations by rule and severity."""
    q = """
    MATCH (sc:Scene)-[:HAS_FLAG]->(f:ComplianceFlag)
    MATCH (sc)-[:SEGMENT_OF]->(v:Video)
    RETURN f.rule as rule, f.severity as severity,
           count(*) as count, collect(DISTINCT v.category)[..5] as categories
    ORDER BY count DESC
    """
    with db.driver.session() as s:
        recs = s.run(q)
        summary = [dict(r) for r in recs]
    return {"summary": summary, "track": "compliance"}


@app.post("/compliance/check/{video_id}")
async def run_compliance_check(video_id: str):
    """Run on-demand compliance check for a specific video."""
    with db.driver.session() as s:
        rec = s.run(
            "MATCH (v:Video {video_id: $vid}) RETURN v.twelvelabs_video_id as tl_id",
            vid=video_id
        ).single()
    if not rec or not rec["tl_id"]:
        raise HTTPException(status_code=404, detail="Video not found or not indexed")

    flags = await tl_service.check_compliance(rec["tl_id"])
    return {"video_id": video_id, "flags": flags, "count": len(flags)}


# ── Compliance — Custom Rules + Explainability + Human Review ─────────────────

# In-memory rule store (replace with Neo4j persistence in production)
_custom_rules: Dict[str, Any] = {}
_review_decisions: Dict[str, Any] = {}

PREDEFINED_RULESETS = {
    "broadcast_standards": [
        {"id": "bs_alcohol",   "rule": "No visible alcohol branding in content targeted to audiences under 21", "severity": "high",     "category": "alcohol"},
        {"id": "bs_violence",  "rule": "Flag graphic violence or blood without proper rating disclosure",       "severity": "critical", "category": "violence"},
        {"id": "bs_language",  "rule": "Detect language that violates broadcast decency standards",             "severity": "high",     "category": "language"},
        {"id": "bs_tobacco",   "rule": "Flag tobacco use or branding in general audience content",             "severity": "high",     "category": "tobacco"},
    ],
    "brand_guidelines": [
        {"id": "bg_competitor","rule": "Detect unauthorized use of competitor brands or trademarks",           "severity": "critical", "category": "brand_safety"},
        {"id": "bg_logo",      "rule": "Flag uncleared third-party logos visible for more than 2 seconds",    "severity": "high",     "category": "brand_safety"},
        {"id": "bg_messaging", "rule": "Detect messaging inconsistent with brand tone or values",             "severity": "medium",   "category": "brand_safety"},
    ],
    "platform_policies": [
        {"id": "pp_hate",      "rule": "Identify language or imagery that violates platform hate speech policies", "severity": "critical", "category": "hate_speech"},
        {"id": "pp_minor",     "rule": "Flag inappropriate content involving minors",                          "severity": "critical", "category": "child_safety"},
        {"id": "pp_copyright", "rule": "Detect unauthorized use of copyrighted music or visual content",       "severity": "high",     "category": "copyright"},
        {"id": "pp_misleading","rule": "Flag potentially misleading or deceptive claims",                      "severity": "medium",   "category": "misinformation"},
    ],
}

RISK_WEIGHTS = {"critical": 10, "high": 5, "medium": 2, "low": 1}


@app.get("/compliance/rulesets")
async def list_rulesets():
    """Return all predefined and custom compliance rulesets."""
    return {
        "predefined":  PREDEFINED_RULESETS,
        "custom":      list(_custom_rules.values()),
        "total_rules": sum(len(v) for v in PREDEFINED_RULESETS.values()) + len(_custom_rules),
    }


@app.post("/compliance/rules")
async def create_custom_rule(body: Dict[str, Any]):
    """
    Create a custom compliance rule.
    Body: {id, rule, severity, category, description?}
    Example: {"rule": "No visible alcohol branding in content for under-21 audiences",
              "severity": "high", "category": "alcohol"}
    """
    rule_id = body.get("id") or f"custom_{len(_custom_rules):04d}"
    rule = {
        "id":          rule_id,
        "rule":        body.get("rule", ""),
        "severity":    body.get("severity", "medium"),
        "category":    body.get("category", "custom"),
        "description": body.get("description", ""),
        "created_at":  "now",
    }
    _custom_rules[rule_id] = rule
    return {"created": rule}


@app.post("/compliance/check/{video_id}/explain")
async def run_compliance_with_explanation(
    video_id: str,
    ruleset: str = "broadcast_standards",
    custom_rules: Optional[str] = None,
):
    """
    Run compliance check with full explainability.
    Returns violations with:
    - precise timestamps
    - human-readable reasoning
    - evidence description
    - severity score
    - remediation suggestion
    ruleset: broadcast_standards | brand_guidelines | platform_policies | all
    """
    with db.driver.session() as s:
        rec = s.run(
            "MATCH (v:Video {video_id: $vid}) RETURN v.twelvelabs_video_id as tl_id, v.title as title",
            vid=video_id
        ).single()
    if not rec or not rec["tl_id"]:
        raise HTTPException(404, "Video not indexed in TwelveLabs")

    # Collect rules to check
    rules_to_check = []
    if ruleset == "all":
        for rules in PREDEFINED_RULESETS.values():
            rules_to_check.extend(rules)
    elif ruleset in PREDEFINED_RULESETS:
        rules_to_check = PREDEFINED_RULESETS[ruleset]

    # Add custom rules if specified
    if custom_rules:
        for rule_id in custom_rules.split(","):
            if rule_id.strip() in _custom_rules:
                rules_to_check.append(_custom_rules[rule_id.strip()])

    # Add all custom rules if no custom_rules filter
    if not custom_rules:
        rules_to_check.extend(_custom_rules.values())

    # Build explainability prompt
    rules_text = "\n".join([
        f"- Rule {r['id']} [{r['severity'].upper()}]: {r['rule']}"
        for r in rules_to_check
    ])

    import anthropic as ant
    client = ant.Anthropic(api_key=settings.anthropic_api_key)

    # Get basic flags from TwelveLabs
    tl_flags = await tl_service.check_compliance(rec["tl_id"],
                                                   rules=[r["category"] for r in rules_to_check])

    # Get Neo4j segment context
    with db.driver.session() as _s:
        _scenes = _s.run("MATCH (v:Video {video_id: $vid})-[:HAS_SCENE]->(sc:Scene) RETURN sc.segment_type as t, sc.t_start as ts, sc.label as lb ORDER BY sc.t_start LIMIT 15", vid=video_id).data()
    _seg_ctx = "; ".join([f"{s['t']}@{int(s['ts'])}s:{s['lb']}" for s in _scenes]) if _scenes else "no segments"

    # Use Opus to generate explainable analysis
    explain_prompt = f"""You are a broadcast compliance expert reviewing video content.

Video: {rec.get('title', video_id)}
    Video segments: {_seg_ctx}
TwelveLabs detection results: {tl_flags}

Compliance rules to evaluate:
{rules_text}

For each potential violation detected, provide:
1. rule_id: which rule was violated
2. t_start: timestamp in seconds where violation begins
3. t_end: timestamp in seconds where violation ends
4. severity: critical|high|medium|low
5. explanation: specific human-readable reasoning (e.g., "Beer bottle visible at 3:42 in scene with minors present")
6. evidence: what visual/audio evidence supports this finding
7. confidence: 0.0-1.0
8. remediation: specific action to resolve (e.g., "Blur bottle at 3:40-3:45" or "Add age rating disclosure")
9. false_positive_risk: low|medium|high (how likely this is a false positive)

Return ONLY a JSON array of violation objects. Return [] if no violations found."""

    violations = []
    try:
        resp = client.messages.create(
            model="claude-opus-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": explain_prompt}]
        )
        raw = resp.content[0].text
        import re, json as _json
        m = re.search(r'\[.*\]', raw, re.DOTALL)
        if m:
            violations = _json.loads(m.group())
    except Exception as e:
        logger.warning("compliance_explain_error", error=str(e)[:100])
        # Fall back to TwelveLabs flags
        violations = [{
            "rule_id": f["rule"],
            "t_start": f.get("t_start", 0),
            "t_end": f.get("t_end", 0),
            "severity": f.get("severity", "medium"),
            "explanation": f.get("explanation", "Detected by TwelveLabs Pegasus"),
            "evidence": "Visual/audio analysis",
            "confidence": 0.75,
            "remediation": "Manual review required",
            "false_positive_risk": "medium",
        } for f in tl_flags]

    # Compute risk score
    risk_score = sum(RISK_WEIGHTS.get(v.get("severity", "low"), 1) for v in violations)
    risk_level = "clean" if risk_score == 0 else \
                 "low" if risk_score <= 3 else \
                 "medium" if risk_score <= 8 else \
                 "high" if risk_score <= 15 else "critical"

    # Persist violations to Neo4j
    for v in violations:
        scene_id = f"{video_id}_comp_{v.get('t_start', 0):.0f}"
        with db.driver.session() as s:
            s.run("""
                MERGE (f:ComplianceFlag {flag_id: $fid})
                SET f.rule = $rule, f.severity = $sev,
                    f.t_start = $ts, f.t_end = $te,
                    f.explanation = $expl, f.evidence = $evid,
                    f.confidence = $conf, f.remediation = $rem,
                    f.false_positive_risk = $fpr,
                    f.review_status = 'pending',
                    f.ruleset = $ruleset
                WITH f
                MATCH (v:Video {video_id: $vid})
                MERGE (f)-[:FLAGS_VIDEO]->(v)
            """,
                fid=scene_id, rule=v.get("rule_id", "unknown"),
                sev=v.get("severity", "medium"),
                ts=float(v.get("t_start", 0)), te=float(v.get("t_end", 0)),
                expl=v.get("explanation", ""), evid=v.get("evidence", ""),
                conf=float(v.get("confidence", 0.75)),
                rem=v.get("remediation", ""), fpr=v.get("false_positive_risk", "medium"),
                vid=video_id, ruleset=ruleset,
            )

    return {
        "video_id":      video_id,
        "ruleset":       ruleset,
        "rules_checked": len(rules_to_check),
        "violations":    violations,
        "violation_count": len(violations),
        "risk_score":    risk_score,
        "risk_level":    risk_level,
        "track":         "compliance",
    }


@app.post("/compliance/review/{flag_id}")
async def human_review_decision(
    flag_id: str,
    body: Dict[str, Any] = None,
):
    """
    Record human reviewer decision on a compliance flag.
    Body: {decision: approve|reject|escalate, reviewer: str, note: str}
    - approve: confirmed violation, content needs remediation
    - reject: false positive, flag dismissed
    - escalate: needs senior review / legal team
    """
    body = body or {}
    decision = body.get("decision", "")
    if decision not in ("approve", "reject", "escalate"):
        raise HTTPException(400, "decision must be: approve | reject | escalate")

    record = {
        "flag_id":   flag_id,
        "decision":  decision,
        "reviewer":  body.get("reviewer", "anonymous"),
        "note":      body.get("note", ""),
        "timestamp": "now",
    }
    _review_decisions[flag_id] = record

    # Update Neo4j flag status
    with db.driver.session() as s:
        s.run("""
            MATCH (f:ComplianceFlag {flag_id: $fid})
            SET f.review_status = $status,
                f.reviewer = $reviewer,
                f.review_note = $note
        """, fid=flag_id, status=decision,
             reviewer=record["reviewer"], note=record["note"])

    return {"recorded": record, "track": "compliance"}


@app.get("/compliance/audit")
async def compliance_audit_trail(video_id: Optional[str] = None, limit: int = 50):
    """
    Return full audit trail of compliance decisions.
    Includes: flag details, reviewer decisions, timestamps.
    Suitable for regulatory reconstruction.
    """
    q = """
    MATCH (f:ComplianceFlag)
    WHERE f.review_status IS NOT NULL
    """
    if video_id:
        q += " MATCH (f)-[:FLAGS_VIDEO]->(v:Video {video_id: $vid})"
    q += """
    RETURN f.flag_id, f.rule, f.severity, f.t_start, f.t_end,
           f.explanation, f.confidence, f.review_status,
           f.reviewer, f.review_note, f.ruleset
    ORDER BY f.t_start LIMIT $limit
    """
    with db.driver.session() as s:
        recs = s.run(q, vid=video_id, limit=limit)
        trail = [dict(r) for r in recs]
    return {
        "audit_trail": trail,
        "count": len(trail),
        "video_id": video_id,
        "track": "compliance",
    }


@app.get("/compliance/risk-scores")
async def risk_scores(limit: int = 20):
    """
    Return videos ranked by compliance risk score.
    Risk score = sum of severity weights across all flags.
    """
    q = """
    MATCH (f:ComplianceFlag)-[:FLAGS_VIDEO]->(v:Video)
    WHERE f.review_status <> 'reject' OR f.review_status IS NULL
    WITH v, collect(f) as flags,
         sum(CASE f.severity
             WHEN 'critical' THEN 10
             WHEN 'high'     THEN 5
             WHEN 'medium'   THEN 2
             ELSE 1 END) as risk_score
    RETURN v.video_id, v.title, v.category, v.url,
           risk_score, size(flags) as flag_count,
           [f IN flags | f.severity] as severities
    ORDER BY risk_score DESC LIMIT $limit
    """
    with db.driver.session() as s:
        recs = s.run(q, limit=limit)
        results = [dict(r) for r in recs]

    for r in results:
        score = r.get("risk_score", 0)
        r["risk_level"] = (
            "critical" if score > 15 else
            "high"     if score > 8  else
            "medium"   if score > 3  else
            "low"      if score > 0  else "clean"
        )
    return {"risk_scores": results, "count": len(results), "track": "compliance"}


# ── Advertiser Briefs ─────────────────────────────────────────────────────────

@app.get("/briefs")
async def list_briefs(
    category: Optional[str] = None,
    min_cpm: float = 0,
    limit: int = 50,
):
    """Return all ZeroClick advertiser briefs."""
    q = """
    MATCH (v:Video)-[:HAS_BRIEF]->(ab:AdvertBrief)
    WHERE ab.estimated_cpm >= $min_cpm
    """
    if category:
        q += " AND v.category = $category"
    q += """
    RETURN v.video_id, v.title, v.url, v.category, v.viral_score,
           v.view_count, ab.headline, ab.placement_moment, ab.target_verticals,
           ab.estimated_cpm, ab.zeroclick_context
    ORDER BY ab.estimated_cpm DESC LIMIT $limit
    """
    with db.driver.session() as s:
        recs = s.run(q, min_cpm=min_cpm, category=category, limit=limit)
        briefs = [dict(r) for r in recs]
    return {"briefs": briefs, "count": len(briefs)}


@app.get("/briefs/{video_id}")
async def get_brief(video_id: str):
    with db.driver.session() as s:
        rec = s.run(
            """MATCH (v:Video {video_id: $vid})-[:HAS_BRIEF]->(ab:AdvertBrief)
               RETURN v.video_id, v.title, v.url, v.category, v.viral_score,
                      ab.headline, ab.placement_moment, ab.target_verticals,
                      ab.estimated_cpm, ab.zeroclick_context""",
            vid=video_id
        ).single()
    if not rec:
        raise HTTPException(status_code=404, detail="Brief not found")
    return dict(rec)


# ── Ontology Inference (Opus 4.6) ─────────────────────────────────────────────

@app.post("/ontology/infer")
async def ontology_infer():
    """
    Call Opus 4.6 to reason across the full corpus and propose
    Neo4j schema extensions — new node types, relationships, properties.
    Applies the patch to the live graph automatically.
    """
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=400,
            detail="ANTHROPIC_API_KEY not set. Add it to .env to enable Opus 4.6.")

    snapshot = db.get_corpus_snapshot()
    result = await infer_ontology(
        current_schema=snapshot["current_schema"],
        scene_label_sample=snapshot["scene_labels"],
        tag_frequency=snapshot["tag_frequency"],
        mood_distribution=snapshot["mood_distribution"],
        top_hooks=snapshot["top_hooks"],
    )

    patch = result.get("patch", {})
    if "error" not in patch:
        counts = db.apply_ontology_patch(patch)
        result["applied"] = counts
    else:
        result["applied"] = None

    logger.info("ontology_infer_endpoint_complete",
                new_nodes=len(patch.get("new_node_types", [])))
    return {
        "status": "complete",
        "patch": patch,
        "applied": result.get("applied"),
        "reasoning_summary": patch.get("reasoning_summary", ""),
    }


@app.get("/ontology/schema")
async def get_current_schema():
    """Return current graph schema stats."""
    snapshot = db.get_corpus_snapshot()
    return {
        "schema": snapshot["current_schema"],
        "corpus_stats": {
            "scene_labels_count": len(snapshot["scene_labels"]),
            "unique_tags": len(snapshot["tag_frequency"]),
            "top_hooks_available": len(snapshot["top_hooks"]),
        }
    }


@app.get("/ontology/viral-formats")
async def get_viral_formats():
    """Return all ViralFormat nodes discovered by Opus."""
    with db.driver.session() as s:
        recs = s.run(
            """MATCH (f:ViralFormat)
               OPTIONAL MATCH (v:Video)-[r:USES_FORMAT]->(f)
               RETURN f.name, f.pattern_description, f.avg_viral_score,
                      f.advertiser_value, count(v) as video_count,
                      avg(r.confidence) as avg_confidence
               ORDER BY video_count DESC"""
        )
        return {"viral_formats": [dict(r) for r in recs]}


# ── Campaign Matching (Opus 4.6) ──────────────────────────────────────────────

class CampaignBriefRequest(BaseModel):
    name: str
    advertiser: str
    vertical: str
    target_audience: str
    budget_usd: float
    max_cpm: float = 5.0
    brand_safety_level: str = "standard"    # strict | standard | relaxed
    preferred_categories: List[str] = []
    ad_format: str = "both"                 # bumper | preroll | both
    campaign_objective: str = "awareness"   # awareness | consideration | conversion
    activate_on_networks: bool = False       # True = also create GAM/TTD deals
    networks: List[str] = ["gam", "ttd"]    # which networks to activate on


@app.post("/campaigns/match")
async def match_campaign(req: CampaignBriefRequest, request: Request):
    """
    Opus 4.6 reasons across your full video inventory and returns
    a ranked media plan. Requires x402 USDC payment ($0.50) when enforced.
    """
    gate_resp = await x402_gate.gate(request, "campaign_match")
    if gate_resp:
        return gate_resp
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=400,
            detail="ANTHROPIC_API_KEY not set. Add it to .env to enable Opus 4.6.")

    # Pull inventory + compliance flags
    inventory = db.get_videos_paginated(skip=0, limit=200)
    compliance_flags = db.get_compliance_flags()

    campaign_brief = req.model_dump()
    campaign_id = f"campaign_{uuid.uuid4().hex[:12]}"

    # Run Opus 4.6 with extended thinking
    result = await match_campaign_to_inventory(
        campaign_brief=campaign_brief,
        inventory_snapshot=inventory,
        compliance_flags=compliance_flags,
        top_n=20,
    )
    media_plan = result.get("media_plan", {})

    if "error" in media_plan:
        raise HTTPException(status_code=500,
            detail=f"Opus matching failed: {media_plan.get('error')}")

    # Persist campaign + placements to Neo4j
    campaign_data = {
        **campaign_brief,
        "total_estimated_reach": media_plan.get("total_estimated_reach", 0),
        "total_estimated_spend": media_plan.get("total_estimated_spend", 0),
        "weighted_audience_match": media_plan.get("weighted_audience_match", 0),
    }
    db.upsert_campaign(campaign_id, campaign_data)

    for p in media_plan.get("placements", []):
        db.link_campaign_placement(
            campaign_id=campaign_id,
            video_id=p.get("video_id", ""),
            rank=p.get("rank", 99),
            audience_match=p.get("audience_match_score", 0),
            estimated_spend=p.get("estimated_spend", 0),
        )

    # Optionally activate on ad networks
    network_results = {}
    if req.activate_on_networks:
        if "ttd" in req.networks:
            ttd_result = await ttd_service.create_campaign_from_plan(
                media_plan=media_plan,
                campaign_brief=campaign_brief,
            )
            network_results["ttd"] = ttd_result

            # Write deals back to Neo4j
            for deal in ttd_result.get("results", []):
                if deal.get("deal_id"):
                    revenue_tracker.upsert_deal(
                        video_id=deal["video_id"],
                        platform="the_trade_desk",
                        deal_id=deal["deal_id"],
                        deal_spec={"TargetCPM": req.max_cpm, "FloorCPM": req.max_cpm * 0.8},
                    )

        if "gam" in req.networks:
            gam_results = []
            for p in media_plan.get("placements", [])[:5]:   # GAM: top 5 only
                brief_data = {"ab.estimated_cpm": p.get("estimated_cpm", 3.0),
                              "ab.placement_moment": p.get("timestamp_seconds", 0),
                              "ab.zeroclick_context": p.get("zeroclick_signal", ""),
                              "target_verticals": [req.vertical]}
                video_data = {"v.video_id": p.get("video_id",""),
                              "v.category": p.get("category",""),
                              "v.viral_score": p.get("audience_match_score", 0),
                              "v.view_count": p.get("estimated_reach", 0)}
                gam_res = await gam_service.create_line_item(
                    brief=brief_data, video_meta=video_data,
                    order_id=settings.gam_order_id or None,
                )
                gam_results.append(gam_res)
                if gam_res.get("line_item_id"):
                    revenue_tracker.upsert_deal(
                        video_id=p.get("video_id",""),
                        platform="google_ad_manager",
                        deal_id=gam_res["line_item_id"],
                        deal_spec={"TargetCPM": p.get("estimated_cpm", 3.0),
                                   "FloorCPM": p.get("estimated_cpm", 3.0) * 0.8},
                    )
            network_results["gam"] = gam_results

    logger.info("campaign_match_complete",
                campaign_id=campaign_id,
                placements=len(media_plan.get("placements", [])),
                networks_activated=list(network_results.keys()))

    return {
        "campaign_id": campaign_id,
        "status": "created",
        "media_plan": media_plan,
        "network_activation": network_results,
        "executive_summary": media_plan.get("executive_summary", ""),
    }


@app.get("/campaigns")
async def list_campaigns(limit: int = 50):
    """List all campaigns with placement counts and performance."""
    return {"campaigns": db.get_campaigns(limit)}


@app.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Get full campaign detail including all ranked placements."""
    placements = db.get_campaign_placements(campaign_id)
    campaigns = db.get_campaigns(limit=200)
    meta = next((c for c in campaigns
                 if c.get("c.campaign_id") == campaign_id), None)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"campaign": meta, "placements": placements}


# ── Ad Network — deals + revenue ─────────────────────────────────────────────

@app.post("/deals/activate/{video_id}")
async def activate_deal(
    video_id: str,
    networks: str = "gam,ttd",   # comma-separated
):
    """
    Activate a single video's ZeroClick brief on GAM and/or TTD.
    Path A revenue: creates a live line item / PMP deal.
    """
    with db.driver.session() as s:
        rec = s.run(
            """MATCH (v:Video {video_id: $vid})-[:HAS_BRIEF]->(ab:AdvertBrief)
               RETURN v.video_id, v.title, v.url, v.category, v.viral_score,
                      v.view_count, ab.headline, ab.placement_moment,
                      ab.target_verticals, ab.estimated_cpm, ab.zeroclick_context""",
            vid=video_id
        ).single()
    if not rec:
        raise HTTPException(status_code=404,
            detail="Video not found or no brief generated yet")

    brief  = dict(rec)
    video_meta = dict(rec)
    results = {}
    net_list = [n.strip() for n in networks.split(",")]

    if "ttd" in net_list:
        ttd_res = await ttd_service.create_pmp_deal(brief, video_meta)
        results["ttd"] = ttd_res
        if ttd_res.get("deal_id"):
            revenue_tracker.upsert_deal(
                video_id=video_id,
                platform="the_trade_desk",
                deal_id=ttd_res["deal_id"],
                deal_spec=ttd_res.get("deal_spec", {}),
            )

    if "gam" in net_list:
        gam_res = await gam_service.create_line_item(brief, video_meta)
        results["gam"] = gam_res
        if gam_res.get("line_item_id"):
            revenue_tracker.upsert_deal(
                video_id=video_id,
                platform="google_ad_manager",
                deal_id=gam_res["line_item_id"],
                deal_spec=gam_res.get("targeting_summary", {}),
            )

    return {"video_id": video_id, "status": "activated", "results": results}


@app.get("/deals")
async def list_deals(limit: int = 50):
    """All active ad deals across GAM and TTD."""
    return {"deals": revenue_tracker.get_deal_list(limit)}


@app.get("/revenue")
async def revenue_dashboard():
    """Aggregate revenue dashboard — impressions + spend by platform."""
    return db.get_revenue_dashboard()


@app.get("/revenue/deals/{deal_id}/refresh")
async def refresh_deal_stats(deal_id: str, platform: str = "ttd"):
    """Pull latest impression/spend stats for a deal from the ad network."""
    if platform == "ttd":
        stats = await ttd_service.get_deal_stats(deal_id)
    else:
        stats = await gam_service.get_delivery_stats(deal_id)

    # Update Neo4j with fresh stats
    with db.driver.session() as s:
        s.run(
            """MATCH (d:AdDeal {deal_id: $did})
               SET d.impressions = $impressions,
                   d.revenue_usd = $revenue_usd,
                   d.win_rate    = $win_rate,
                   d.updated_at  = timestamp()""",
            did=deal_id,
            impressions=stats.get("impressions", 0),
            revenue_usd=stats.get("revenue_usd", 0),
            win_rate=stats.get("win_rate", 0),
        )
    return {"deal_id": deal_id, "stats": stats}


# ── Trend detection (Opus 4.6) ────────────────────────────────────────────────

@app.post("/trends/detect")
async def detect_trend_report(request: Request):
    """
    Run Opus 4.6 trend emergence detector.
    Requires x402 USDC payment ($0.25) when enforced.
    """
    gate_resp = await x402_gate.gate(request, "trend_detect")
    if gate_resp:
        return gate_resp
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=400,
            detail="ANTHROPIC_API_KEY not set.")

    current = db.get_corpus_snapshot()
    # For MVP, use the same snapshot as "previous week" — in production
    # you'd store weekly snapshots in Redis or a separate Neo4j label.
    previous = {
        "scene_labels": current["scene_labels"][:100],
        "tag_frequency": dict(list(current["tag_frequency"].items())[50:]),
        "top_hooks": current["top_hooks"][25:],
    }

    result = await detect_trends(
        current_week_data=current,
        previous_week_data=previous,
    )
    return {
        "status": "complete",
        "trend_report": result.get("trend_report", {}),
    }


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "viral-video-intelligence"}


# ── Circle / USDC wallet ──────────────────────────────────────────────────────

@app.get("/circle/wallet")
async def circle_wallet():
    """Platform USDC treasury balance on Circle Arc testnet."""
    balance = await circle_service.get_wallet_balance()
    return balance


@app.post("/circle/payment-intent")
async def create_payment_intent(query_type: str = "semantic_search"):
    """
    Create a Circle USDC payment intent.
    Returns deposit address + amount for the caller to fund.
    AI agents call this before making a paid API request.
    """
    amount = PAYMENT_TIERS.get(query_type, settings.x402_price_per_query)
    intent = await circle_service.create_payment_intent(
        amount_usdc=amount,
        query_type=query_type,
    )
    return intent


@app.get("/circle/verify/{transfer_id}")
async def verify_payment(transfer_id: str, query_type: str = "semantic_search"):
    """
    Verify a USDC transfer was received.
    Call this after sending USDC to confirm before making the paid request.
    """
    amount = PAYMENT_TIERS.get(query_type, settings.x402_price_per_query)
    result = await circle_service.verify_transfer(transfer_id, amount)
    return result


@app.get("/circle/transactions")
async def circle_transactions(limit: int = 20):
    """Recent USDC inflows to the platform wallet."""
    return await circle_service.get_transaction_history(limit)


# ── x402 micropayment stats ───────────────────────────────────────────────────

@app.get("/x402/stats")
async def x402_stats():
    """
    Revenue from x402 micropayments — total USDC earned per query type.
    This is the per-query monetisation layer on top of SaaS subscriptions.
    """
    return x402_gate.get_payment_stats()


@app.get("/x402/pricing")
async def x402_pricing():
    """Current pricing per query type in USDC."""
    return {
        "pricing": PAYMENT_TIERS,
        "enforcement": settings.x402_enforce_payment,
        "environment": settings.circle_environment,
        "chain": "ARB",
        "payment_flow": [
            "1. GET /x402/pricing — see prices",
            "2. POST /circle/payment-intent?query_type=semantic_search — get deposit address",
            "3. Send USDC to deposit_address on Arbitrum",
            "4. GET /circle/verify/{transfer_id} — confirm payment",
            "5. Call paid endpoint with header: X-Payment-Transfer-Id: {transfer_id}",
            "6. In testnet demo: use transfer_id='sim_anything' to bypass",
        ],
    }


# ── MCP server manifest — AI agent discovery ─────────────────────────────────

@app.get("/.well-known/mcp.json")
async def mcp_manifest():
    """
    MCP server manifest. AI agents (Claude, GPT agents, buying bots)
    discover available tools and their x402 prices here.

    This is how MEV Shield's x402 architecture works — same pattern,
    applied to video intelligence instead of mempool data.
    """
    return {
        "mcp_version": "1.0",
        "server_name": "viral-video-intelligence",
        "description": "TwelveLabs × Neo4j × ZeroClick.ai — viral short-form video intelligence for advertisers and AI buying agents",
        "pricing_model": "x402_per_query_usdc",
        "chain": "ARB",
        "circle_environment": settings.circle_environment,
        "platform_wallet": circle_service.wallet_id or "configure_CIRCLE_WALLET_ID",
        "tools": MCP_TOOLS,
        "authentication": {
            "type": "x402",
            "header": "X-Payment-Transfer-Id",
            "payment_intent_endpoint": "/circle/payment-intent",
            "verify_endpoint": "/circle/verify/{transfer_id}",
        },
    }


# ── LTX — AI creative generation ─────────────────────────────────────────────

class CreativeRequest(BaseModel):
    video_id: str
    ad_format: str = "6s_bumper"   # 6s_bumper | 15s_preroll | thumbnail

@app.post("/creatives/generate/{video_id}")
async def generate_creative(video_id: str, ad_format: str = "6s_bumper"):
    """
    Generate a matched video ad creative using LTX AI.
    Takes the ZeroClick brief + TwelveLabs context for this video
    and produces a 6s bumper or 15s pre-roll that visually matches
    the placement moment's mood, objects, and palette.
    Stores result as (:Creative) node in Neo4j.
    """
    with db.driver.session() as s:
        rec = s.run(
            """MATCH (v:Video {video_id: $vid})
               OPTIONAL MATCH (v)-[:HAS_BRIEF]->(ab:AdvertBrief)
               RETURN v.video_id, v.title, v.url, v.category, v.viral_score,
                      v.view_count, v.duration, v.thumbnail_url,
                      v.twelvelabs_video_id,
                      ab.headline, ab.placement_moment, ab.target_verticals,
                      ab.estimated_cpm, ab.zeroclick_context""",
            vid=video_id
        ).single()
    if not rec:
        raise HTTPException(status_code=404, detail="Video not found")

    video_meta = dict(rec)
    brief = {
        "ab.estimated_cpm":    rec["ab.estimated_cpm"] or 3.0,
        "ab.placement_moment": rec["ab.placement_moment"] or 0,
        "ab.headline":         rec["ab.headline"] or "",
        "ab.zeroclick_context": rec["ab.zeroclick_context"] or "",
        "target_verticals":    rec["ab.target_verticals"] or [],
    }

    # Extract TwelveLabs context if available
    tl_ctx = {}
    if rec.get("v.twelvelabs_video_id"):
        try:
            tl_ctx = await tl_service.extract_advertiser_context(
                rec["v.twelvelabs_video_id"]
            )
        except Exception:
            pass

    creative = await ltx_service.generate_creative(
        brief=brief,
        tl_context=tl_ctx,
        video_meta=video_meta,
        ad_format=ad_format,
    )

    # Store (:Creative) node in Neo4j
    with db.driver.session() as s:
        s.run(
            """MERGE (c:Creative {creative_id: $cid})
               SET c += {video_url: $vurl, thumbnail_url: $turl,
                         ad_format: $fmt, duration: $dur, status: $status,
                         provider: 'ltx', generated_at: timestamp()}
               WITH c
               MATCH (v:Video {video_id: $vid})
               MERGE (v)-[:HAS_CREATIVE]->(c)""",
            cid=creative["creative_id"],
            vurl=creative.get("video_url", ""),
            turl=creative.get("thumbnail_url", ""),
            fmt=ad_format,
            dur=creative.get("duration", 6),
            status=creative.get("status", "ready"),
            vid=video_id,
        )

    # Register with TrackIt CDN
    cdn = await trackit_engine.register_creative_cdn(creative, video_id)
    creative["cdn_url"] = cdn.get("cdn_url", creative.get("video_url", ""))

    logger.info("creative_generated", video_id=video_id, creative_id=creative["creative_id"])
    return {"video_id": video_id, "creative": creative, "cdn": cdn}


@app.post("/creatives/campaign/{campaign_id}")
async def generate_campaign_creatives(campaign_id: str, ad_format: str = "6s_bumper"):
    """
    Generate LTX creatives for all placements in an Opus campaign plan.
    One creative per ranked placement, all matched to moment context.
    """
    placements = db.get_campaign_placements(campaign_id)
    if not placements:
        raise HTTPException(status_code=404, detail="Campaign not found or no placements")

    creatives = await ltx_service.generate_campaign_creatives(placements, ad_format)
    return {
        "campaign_id": campaign_id,
        "creatives_generated": len(creatives),
        "ad_format": ad_format,
        "creatives": creatives,
    }


@app.get("/creatives/video/{video_id}")
async def get_video_creatives(video_id: str):
    """List all generated creatives for a video."""
    with db.driver.session() as s:
        recs = s.run(
            """MATCH (v:Video {video_id: $vid})-[:HAS_CREATIVE]->(c:Creative)
               RETURN c.creative_id, c.video_url, c.thumbnail_url,
                      c.ad_format, c.duration, c.status, c.generated_at
               ORDER BY c.generated_at DESC""",
            vid=video_id
        )
        return {"video_id": video_id, "creatives": [dict(r) for r in recs]}


# ── TrackIt — workflow + MAM + CDN + audit ────────────────────────────────────

@app.post("/trackit/workflow/{video_id}")
async def submit_workflow(video_id: str):
    """
    Submit a video to the TrackIt workflow engine.
    Wraps the ingestion pipeline with fault-tolerant state machine tracking,
    broadcaster audit trail, and SMPTE-aligned MAM metadata output.
    """
    with db.driver.session() as s:
        rec = s.run(
            "MATCH (v:Video {video_id: $vid}) RETURN properties(v) as props",
            vid=video_id
        ).single()
    if not rec:
        raise HTTPException(status_code=404, detail="Video not found")

    video_meta = rec["props"]
    result = await trackit_engine.submit_workflow(video_id, video_meta)
    return result


@app.get("/trackit/workflow/{workflow_id}/status")
async def workflow_status(workflow_id: str):
    """Get pipeline state progress for a TrackIt workflow."""
    return await trackit_engine.get_workflow_status(workflow_id)


@app.post("/trackit/mam/{video_id}")
async def push_mam(video_id: str):
    """
    Push enriched video metadata to broadcaster MAM system.
    Produces SMPTE ST 2067-aligned metadata with TwelveLabs scene data,
    compliance flags, viral scores, and ZeroClick advertiser signals.
    """
    with db.driver.session() as s:
        # Get video + scenes + brief
        v_rec = s.run(
            "MATCH (v:Video {video_id: $vid}) RETURN properties(v) as props",
            vid=video_id
        ).single()
        if not v_rec:
            raise HTTPException(status_code=404, detail="Video not found")

        scene_recs = s.run(
            """MATCH (sc:Scene)-[:SEGMENT_OF]->(v:Video {video_id: $vid})
               RETURN properties(sc) as props ORDER BY sc.t_start""",
            vid=video_id
        )
        segments = [dict(r["props"]) for r in scene_recs]

        flag_recs = s.run(
            """MATCH (sc:Scene)-[:HAS_FLAG]->(f:ComplianceFlag)
               MATCH (sc)-[:SEGMENT_OF]->(v:Video {video_id: $vid})
               RETURN properties(f) as props""",
            vid=video_id
        )
        flags = [dict(r["props"]) for r in flag_recs]

        brief_rec = s.run(
            """MATCH (v:Video {video_id: $vid})-[:HAS_BRIEF]->(ab:AdvertBrief)
               RETURN properties(ab) as props""",
            vid=video_id
        ).single()
        brief = dict(brief_rec["props"]) if brief_rec else None

    video_meta = v_rec["props"]
    video_meta["v.video_id"] = video_id

    result = await trackit_engine.push_to_mam(video_meta, segments, flags, brief)
    return result


@app.get("/trackit/audit")
async def get_audit_trail(video_id: Optional[str] = None, limit: int = 100):
    """
    Broadcaster-grade immutable audit trail.
    Every pipeline step, compliance decision, creative generation,
    and deal activation is logged here for regulatory compliance.
    """
    records = trackit_engine.get_audit_trail(video_id)
    return {
        "records": records[-limit:],
        "count": len(records),
        "video_id": video_id,
    }


@app.get("/trackit/qoe/{video_id}")
async def qoe_metrics(video_id: str):
    """Quality of Experience metrics for a video (proxy score + VMAF in production)."""
    with db.driver.session() as s:
        rec = s.run(
            "MATCH (v:Video {video_id: $vid}) RETURN properties(v) as props",
            vid=video_id
        ).single()
    if not rec:
        raise HTTPException(status_code=404, detail="Video not found")

    qoe = trackit_engine.compute_qoe_score(rec["props"])
    return {"video_id": video_id, "qoe": qoe}


@app.get("/trackit/pipeline-states")
async def pipeline_states():
    """Return the canonical 8-step pipeline state machine definition."""
    return {
        "states": PIPELINE_STATES,
        "count": len(PIPELINE_STATES),
        "description": "TrackIt-orchestrated ViralIntel ingestion pipeline",
    }


@app.get("/")
async def root():
    return {
        "name": "Viral Video Intelligence",
        "tagline": "TwelveLabs × Neo4j × ZeroClick.ai × Circle × LTX × TrackIt — NAB 2026",
        "tracks": ["search", "segmentation", "compliance"],
        "revenue_layers": [
            "x402 USDC micropayments (Circle Arc)",
            "GAM contextual line items",
            "TTD PMP deals",
            "SaaS subscription (Opus campaign matching)",
        ],
        "creative_layer": "LTX AI video generation",
        "orchestration_layer": "TrackIt workflow + MAM + CDN + audit",
        "mcp_manifest": "/.well-known/mcp.json",
        "docs": "/docs",
    }
# ── ADD THIS BLOCK to backend/main.py after the /pipeline/start endpoint ──────

@app.post("/pipeline/ingest-local")
async def ingest_local_files(folder: str = "/app/data"):
    """
    Ingest all video files from a local folder into TwelveLabs.
    Scans folder/sports, folder/news, folder/production subfolders.
    Each video is indexed with TwelveLabs and saved to Neo4j.
    
    Usage:
        curl -X POST "http://localhost:8008/pipeline/ingest-local"
        curl -X POST "http://localhost:8008/pipeline/ingest-local?folder=/app/data"
    """
    import os
    from pathlib import Path

    VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}

    # Map folder name to category
    CATEGORY_MAP = {
        'sports':     'sports_archive',
        'news':       'news_broadcast',
        'production': 'production_broll',
    }

    # Scan all video files
    data_path = Path(folder)
    if not data_path.exists():
        raise HTTPException(404, f"Folder {folder} not found in container")

    video_files = []
    for path in sorted(data_path.rglob('*')):
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        if path.name.endswith('.part'):
            continue  # Skip incomplete downloads
        category = CATEGORY_MAP.get(path.parent.name, 'archive')
        video_files.append((path, category))

    if not video_files:
        return {"error": "No video files found", "folder": folder,
                "tip": "Make sure videos are in data/sports, data/news, data/production"}

    results = []
    total = len(video_files)
    logger.info("local_ingest_start", total=total, folder=folder)

    for i, (path, category) in enumerate(video_files):
        await asyncio.sleep(5)  # Rate limit protection
        # Clean video_id from filename
        video_id = path.stem[:60].replace(' ', '_').replace('|', '').replace(':', '')
        video_id = ''.join(c for c in video_id if c.isalnum() or c in '_-')
        video_id = f"local_{category[:4]}_{video_id[:40]}"

        logger.info("indexing_local_video", path=str(path), video_id=video_id,
                    progress=f"{i+1}/{total}")

        try:
            # Index with TwelveLabs
            tl_video_id = await tl_service.index_video_from_file(str(path), video_id)

            if tl_video_id:
                # Save to Neo4j
                with db.driver.session() as s:
                    s.run("""
                        MERGE (v:Video {video_id: $vid})
                        SET v.title         = $title,
                            v.category      = $cat,
                            v.twelvelabs_video_id = $tl_id,
                            v.source        = 'local_file',
                            v.file_path     = $fpath,
                            v.file_size_mb  = $size_mb,
                            v.indexed_at    = timestamp()
                        MERGE (c:Category {name: $cat})
                        MERGE (v)-[:IN_CATEGORY]->(c)
                    """,
                    vid=video_id,
                    title=path.stem[:100],
                    cat=category,
                    tl_id=tl_video_id,
                    fpath=str(path),
                    size_mb=round(path.stat().st_size / 1024 / 1024, 1))

                # Run segmentation automatically
                try:
                    content_type_map = {
                        'sports_archive': 'sports',
                        'news_broadcast': 'news',
                        'production_broll': 'studio',
                    }
                    ct = content_type_map.get(category, 'auto')
                    segments = await tl_service.segment_video(tl_video_id, content_type=ct)
                    for j, seg in enumerate(segments):
                        scene_id = f"{video_id}_seg_{j:03d}"
                        with db.driver.session() as s:
                            s.run("""
                                MERGE (sc:Scene {scene_id: $sid})
                                SET sc.video_id     = $vid,
                                    sc.t_start      = $ts, sc.t_end = $te,
                                    sc.segment_type = $stype,
                                    sc.label        = $label,
                                    sc.confidence   = $conf,
                                    sc.viral_segment_score = $score,
                                    sc.is_ad_break_candidate = $ad
                                MERGE (v:Video {video_id: $vid})
                                MERGE (sc)-[:SEGMENT_OF]->(v)
                            """,
                            sid=scene_id, vid=video_id,
                            ts=float(seg.get('t_start', 0)),
                            te=float(seg.get('t_end', 0)),
                            stype=seg.get('segment_type', 'chapter'),
                            label=seg.get('label', '')[:200],
                            conf=float(seg.get('confidence', 0.8)),
                            score=float(seg.get('viral_segment_score', 0.5)),
                            ad=bool(seg.get('is_ad_break_candidate', False)))
                except Exception as seg_err:
                    logger.warning("segmentation_failed", video_id=video_id, error=str(seg_err)[:100])

                results.append({
                    "video_id":   video_id,
                    "title":      path.stem[:80],
                    "category":   category,
                    "tl_video_id": tl_video_id,
                    "status":     "indexed",
                    "file_mb":    round(path.stat().st_size / 1024 / 1024, 1),
                })
                logger.info("video_indexed_ok", video_id=video_id, tl_id=tl_video_id)
            else:
                results.append({
                    "video_id": video_id,
                    "title":    path.stem[:80],
                    "status":   "failed",
                    "error":    "TwelveLabs indexing returned None",
                })
                logger.warning("video_index_failed", video_id=video_id)

        except Exception as e:
            results.append({
                "video_id": video_id,
                "title":    path.stem[:80],
                "status":   "error",
                "error":    str(e)[:200],
            })
            logger.error("video_ingest_error", video_id=video_id, error=str(e)[:200])

    indexed = [r for r in results if r["status"] == "indexed"]
    failed  = [r for r in results if r["status"] != "indexed"]

    return {
        "total_files":   total,
        "indexed":       len(indexed),
        "failed":        len(failed),
        "folder":        folder,
        "results":       results,
        "track":         "local_ingest",
    }


@app.get("/pipeline/ingest-status")
async def ingest_local_status(folder: str = "/app/data"):
    """Check which local files have been indexed vs pending."""
    from pathlib import Path
    VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}

    data_path = Path(folder)
    all_files = [p for p in data_path.rglob('*')
                 if p.suffix.lower() in VIDEO_EXTENSIONS and not p.name.endswith('.part')]

    # Check which are in Neo4j
    indexed_ids = set()
    with db.driver.session() as s:
        recs = s.run("MATCH (v:Video) WHERE v.source = 'local_file' RETURN v.file_path")
        indexed_ids = {r["v.file_path"] for r in recs}

    pending = [str(f) for f in all_files if str(f) not in indexed_ids]
    done    = [str(f) for f in all_files if str(f) in indexed_ids]

    return {
        "total_files": len(all_files),
        "indexed":     len(done),
        "pending":     len(pending),
        "pending_files": pending,
        "indexed_files": done,
    }

