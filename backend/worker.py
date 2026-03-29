"""
RQ background worker — full ingestion pipeline:
  discover → download → TwelveLabs index → segment → comply → brief → Neo4j
"""
import asyncio
import os
import uuid
from typing import Dict, Any, Optional

import redis
from rq import Queue, Worker
from rq.job import Job

from config import settings, VIDEO_CATEGORIES
from database import db
from ingestion import ingestion_service
from twelvelabs_service import tl_service
from zeroclick_service import zeroclick_service
import structlog

logger = structlog.get_logger()

redis_conn = redis.from_url(settings.redis_url)
pipeline_queue = Queue("pipeline", connection=redis_conn)
ingest_queue = Queue("ingest", connection=redis_conn)


# ── Job: Process Single Video ─────────────────────────────────────────────────
def process_single_video(video_meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full pipeline for one video:
    1. Upsert Video + Creator nodes into Neo4j
    2. Upload to TwelveLabs and wait for indexing
    3. Run segmentation → upsert Scene nodes
    4. Run compliance → upsert ComplianceFlag nodes
    5. Extract TL advertiser context
    6. Generate ZeroClick brief → upsert AdvertBrief node
    7. Upsert Trend nodes from tags
    """
    return asyncio.run(_process_single_video_async(video_meta))


async def _process_single_video_async(video_meta: Dict[str, Any]) -> Dict[str, Any]:
    video_id = video_meta["video_id"]
    log = logger.bind(video_id=video_id, category=video_meta.get("category"))
    log.info("pipeline_start")

    try:
        # ── Step 1: Upsert Video node ─────────────────────────────────────
        db_data = {
            "video_id": video_id,
            "title": video_meta.get("title", ""),
            "platform": video_meta.get("platform", "youtube"),
            "url": video_meta.get("url", ""),
            "view_count": video_meta.get("view_count", 0),
            "like_count": video_meta.get("like_count", 0),
            "comment_count": video_meta.get("comment_count", 0),
            "share_count": video_meta.get("share_count", 0),
            "duration": video_meta.get("duration", 0),
            "category": video_meta.get("category", "unknown"),
            "description": video_meta.get("description", ""),
            "upload_date": video_meta.get("upload_date", ""),
            "twelvelabs_video_id": "",
            "viral_score": video_meta.get("viral_score", 0),
            "hook_strength": 0.0,
            "watch_through_rate": 0.0,
            "thumbnail_url": video_meta.get("thumbnail_url", ""),
        }
        db.upsert_video(db_data)

        # ── Step 2: Creator node ──────────────────────────────────────────
        channel_id = video_meta.get("channel_id", f"unknown_{video_id}")
        channel_name = video_meta.get("channel_title", "Unknown Creator")
        db.upsert_creator(
            channel_id=channel_id,
            channel_name=channel_name,
            subscriber_count=0,
            niche=video_meta.get("category", "general"),
        )
        db.link_video_creator(video_id, channel_id)

        # ── Step 3: Trend nodes from tags ────────────────────────────────
        for tag in (video_meta.get("tags") or [])[:10]:
            db.upsert_trend(name=tag.lower(), trend_type="hashtag", video_id=video_id)

        # ── Step 4: TwelveLabs indexing ───────────────────────────────────
        tl_video_id: Optional[str] = None
        watch_url = video_meta.get("watch_url") or video_meta.get("url", "")

        # Try URL indexing first (no download needed)
        if watch_url:
            log.info("tl_indexing_via_url")
            tl_video_id = await tl_service.index_video_from_url(watch_url, video_id)

        # Fallback: download then upload
        if not tl_video_id:
            log.info("tl_fallback_download")
            local_path = ingestion_service.download_video(video_id, watch_url)
            if local_path:
                try:
                    tl_video_id = await tl_service.index_video_from_file(local_path, video_id)
                finally:
                    # Delete local file immediately after upload — no reason to keep it.
                    # TwelveLabs holds the embeddings in the cloud.
                    try:
                        import os
                        if local_path and os.path.exists(str(local_path)):
                            os.remove(str(local_path))
                            log.info("local_file_deleted", path=str(local_path))
                    except Exception as cleanup_err:
                        log.warning("local_file_cleanup_failed", error=str(cleanup_err))

        if not tl_video_id:
            log.warning("tl_indexing_failed_skipping_ml_steps")
            return {"status": "partial", "video_id": video_id, "tl_indexed": False}

        # Update Neo4j with TL video ID
        with db.driver.session() as s:
            s.run("MATCH (v:Video {video_id: $vid}) SET v.twelvelabs_video_id = $tl_vid",
                  vid=video_id, tl_vid=tl_video_id)

        # ── Step 5: Segmentation ──────────────────────────────────────────
        log.info("running_segmentation")
        segments = await tl_service.segment_video(tl_video_id)
        hook_scores = []

        for i, seg in enumerate(segments):
            scene_id = f"{video_id}_scene_{i:03d}"
            scene_data = {
                "scene_id": scene_id,
                "video_id": video_id,
                "t_start": seg.get("t_start", 0),
                "t_end": seg.get("t_end", 0),
                "segment_type": seg.get("segment_type", "chapter"),
                "label": seg.get("label", ""),
                "confidence": seg.get("confidence", 0.5),
                "attention_score": seg.get("attention_score", 0.5),
                "viral_segment_score": seg.get("viral_segment_score", 0),
                "description": seg.get("description", ""),
            }
            db.upsert_scene(scene_data)
            if seg.get("segment_type") == "hook":
                hook_scores.append(seg.get("viral_segment_score", 0))

        hook_strength = max(hook_scores) if hook_scores else 0.0
        with db.driver.session() as s:
            s.run("MATCH (v:Video {video_id: $vid}) SET v.hook_strength = $hs",
                  vid=video_id, hs=hook_strength)

        # ── Step 6: Compliance ────────────────────────────────────────────
        log.info("running_compliance")
        compliance_flags = await tl_service.check_compliance(tl_video_id)
        for flag in compliance_flags:
            scene_candidates = [
                s for s in segments
                if s.get("t_start", 0) <= flag.get("t_start", 0) <= s.get("t_end", 999)
            ]
            scene_id = (
                f"{video_id}_scene_{segments.index(scene_candidates[0]):03d}"
                if scene_candidates else f"{video_id}_scene_000"
            )
            db.add_compliance_flag(
                scene_id=scene_id,
                rule=flag.get("rule", "unknown"),
                severity=flag.get("severity", "low"),
                explanation=flag.get("explanation", ""),
                t_start=flag.get("t_start", 0),
                t_end=flag.get("t_end", 0),
            )

        # ── Step 7: TL advertiser context ────────────────────────────────
        log.info("extracting_advertiser_context")
        tl_context = await tl_service.extract_advertiser_context(tl_video_id)

        # ── Step 8: ZeroClick brief ───────────────────────────────────────
        log.info("generating_zeroclick_brief")
        brief = await zeroclick_service.generate_brief(
            video_meta=video_meta,
            tl_context=tl_context,
            segments=segments,
        )
        db.upsert_advert_brief(video_id=video_id, brief=brief)

        log.info("pipeline_complete", tl_video_id=tl_video_id,
                 scenes=len(segments), flags=len(compliance_flags))
        return {
            "status": "success",
            "video_id": video_id,
            "tl_video_id": tl_video_id,
            "scenes": len(segments),
            "compliance_flags": len(compliance_flags),
            "brief_generated": bool(brief),
        }

    except Exception as e:
        log.error("pipeline_error", error=str(e), exc_info=True)
        return {"status": "error", "video_id": video_id, "error": str(e)}


# ── Job: Discover + Enqueue all videos ────────────────────────────────────────
def run_full_ingestion() -> Dict[str, Any]:
    return asyncio.run(_run_full_ingestion_async())


async def _run_full_ingestion_async() -> Dict[str, Any]:
    logger.info("full_ingestion_started")
    total_enqueued = 0

    for category_key, cat_config in VIDEO_CATEGORIES.items():
        target = cat_config["count"]
        logger.info("discovering_category", category=category_key, target=target)

        videos = await ingestion_service.discover_videos_for_category(
            category_key, target
        )

        for video in videos:
            pipeline_queue.enqueue(
                process_single_video,
                video,
                job_timeout=900,  # 15 min per video
                result_ttl=3600,
            )
            total_enqueued += 1

        logger.info("category_enqueued", category=category_key, count=len(videos))

    logger.info("full_ingestion_enqueued", total=total_enqueued)
    return {"status": "enqueued", "total": total_enqueued}


# ── Worker entrypoint ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    db.init_schema()
    logger.info("worker_starting", queues=["pipeline", "ingest"])
    w = Worker(
        [pipeline_queue, ingest_queue],
        connection=redis_conn,
        log_job_description=True,
    )
    w.work(with_scheduler=True)
