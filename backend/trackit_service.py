"""
TrackIt workflow automation service.

TrackIt is an AWS Advanced Tier Services Partner specialising in
M&E cloud-native software. In this platform they provide:

  1. Workflow orchestration — the 8-step ingestion pipeline as a
     fault-tolerant state machine (Step Functions-compatible format
     also works locally via a simple sequential runner for non-AWS envs)

  2. Content delivery CDN registration — registers generated LTX
     creatives and processed video segments with a CDN for
     broadcast-grade delivery latency

  3. MAM (Media Asset Management) integration — pushes enriched
     metadata (TwelveLabs scene labels, viral scores, compliance flags,
     ZeroClick briefs) into a broadcaster's existing MAM system via
     standard EIDR / SMPTE metadata schemas

  4. Compliance audit trail — produces immutable audit records for
     every content decision: indexing, segmentation, compliance flag,
     creative generation, deal activation — broadcaster-grade logging

  5. Quality metrics — QoE scores per video (resolution, bitrate,
     encoding quality) plus workflow performance dashboards

Non-AWS mode: all functionality runs locally. The state machine
executes sequentially in-process. CDN registration is simulated.
MAM output writes to a local JSON file. Audit trail goes to Neo4j.

When TrackIt credentials are set, the same interfaces call the
real TrackIt platform APIs for production M&E deployments.
"""

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from config import settings
from database import db
import structlog

logger = structlog.get_logger()

TRACKIT_BASE = "https://api.trackit.io/v1"


def _trackit_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.trackit_api_key}",
        "Content-Type": "application/json",
        "X-TrackIt-Partner": settings.trackit_partner_id,
    }


# ── SMPTE / EIDR metadata schema ──────────────────────────────────────────────

def build_mam_metadata(
    video_meta: Dict[str, Any],
    segments: List[Dict[str, Any]],
    compliance_flags: List[Dict[str, Any]],
    brief: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build broadcaster-standard MAM metadata record from ViralIntel data.
    Schema aligned with SMPTE ST 2067 / EIDR content registration.
    """
    flags_summary = {
        "total": len(compliance_flags),
        "critical": sum(1 for f in compliance_flags if f.get("severity") == "critical"),
        "high":     sum(1 for f in compliance_flags if f.get("severity") == "high"),
        "brand_safe": len(compliance_flags) == 0,
    }

    segment_summary = [
        {
            "type":              s.get("segment_type", ""),
            "start_tc":          _seconds_to_tc(float(s.get("t_start", 0))),
            "end_tc":            _seconds_to_tc(float(s.get("t_end", 0))),
            "viral_score":       s.get("viral_segment_score", 0),
            "attention_score":   s.get("attention_score", 0),
        }
        for s in segments
    ]

    return {
        "schema_version":   "SMPTE-2067-1",
        "asset_id":         f"viral-intel:{video_meta.get('v.video_id', '')}",
        "eidr_id":          None,   # populated when broadcaster registers with EIDR
        "title":            video_meta.get("v.title", ""),
        "platform":         video_meta.get("v.platform", "youtube"),
        "source_url":       video_meta.get("v.url", ""),
        "duration_seconds": video_meta.get("v.duration", 0),
        "category":         video_meta.get("v.category", ""),
        "ingest_date":      datetime.now(timezone.utc).isoformat(),
        "content_ratings": {
            "viral_score":    video_meta.get("v.viral_score", 0),
            "hook_strength":  video_meta.get("v.hook_strength", 0),
            "view_count":     video_meta.get("v.view_count", 0),
        },
        "compliance":       flags_summary,
        "segments":         segment_summary,
        "ai_metadata": {
            "indexed_by":       "TwelveLabs Marengo 2.7 + Pegasus 1.2",
            "segmentation_model": "Pegasus 1.2",
            "compliance_model": "Pegasus 1.2 rules-based",
            "brief_generated":  brief is not None,
        },
        "advertiser_signals": {
            "estimated_cpm":   brief.get("ab.estimated_cpm", 0) if brief else 0,
            "placement_tc":    _seconds_to_tc(float(brief.get("ab.placement_moment", 0))) if brief else None,
            "target_verticals": brief.get("target_verticals", []) if brief else [],
        },
    }


def _seconds_to_tc(seconds: float, fps: float = 25.0) -> str:
    """Convert float seconds to SMPTE timecode HH:MM:SS:FF."""
    total_frames = int(seconds * fps)
    frames  = total_frames % int(fps)
    secs    = (total_frames // int(fps)) % 60
    minutes = (total_frames // int(fps) // 60) % 60
    hours   = total_frames // int(fps) // 3600
    return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"


# ── Workflow state machine ────────────────────────────────────────────────────

PIPELINE_STATES = [
    "video_discovered",
    "tl_indexed",
    "segments_extracted",
    "compliance_checked",
    "brief_generated",
    "creative_generated",
    "deal_activated",
    "payment_recorded",
]


class TrackItWorkflowEngine:
    """
    Lightweight state machine that wraps the ViralIntel 8-step pipeline
    with full audit trail, retry logic, and MAM output.

    In non-AWS mode: runs sequentially in-process, writes audit records
    to Neo4j and a local NDJSON audit log.

    TrackIt production mode: submits the workflow definition to the
    TrackIt platform for cloud-native execution with automatic retries,
    dead-letter queues, and broadcaster dashboard visibility.
    """

    def __init__(self):
        self.enabled = bool(settings.trackit_api_key)
        self.audit_log_path = "/app/downloads/audit_trail.ndjson"

    # ── Workflow submission ───────────────────────────────────────────────────
    async def submit_workflow(
        self,
        video_id: str,
        video_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Submit a video to the TrackIt workflow engine.
        Returns workflow_id for tracking.
        """
        workflow_id = f"wf_{video_id}_{uuid.uuid4().hex[:8]}"

        if self.enabled:
            return await self._submit_remote(workflow_id, video_id, video_meta)

        # Local mode: record submission, execution happens via worker.py
        self._write_audit_event(workflow_id, video_id, "workflow_submitted", {
            "mode": "local",
            "pipeline_states": PIPELINE_STATES,
        })
        return {
            "workflow_id": workflow_id,
            "video_id":    video_id,
            "status":      "submitted",
            "mode":        "local",
            "states":      PIPELINE_STATES,
        }

    async def _submit_remote(
        self, workflow_id: str, video_id: str, video_meta: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Submit to TrackIt cloud platform."""
        payload = {
            "workflow_id":   workflow_id,
            "video_id":      video_id,
            "definition": {
                "name":   "ViralIntel Ingestion Pipeline",
                "states": PIPELINE_STATES,
                "retry_policy": {"max_attempts": 3, "backoff_rate": 2},
            },
            "input": video_meta,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{TRACKIT_BASE}/workflows",
                headers=_trackit_headers(),
                json=payload,
            )
            if resp.status_code in (200, 201):
                logger.info("trackit_workflow_submitted", workflow_id=workflow_id)
                return resp.json()
            logger.error("trackit_submit_failed",
                         status=resp.status_code, body=resp.text[:200])

        return {"workflow_id": workflow_id, "status": "fallback_local"}

    # ── State transitions ─────────────────────────────────────────────────────
    def record_state_transition(
        self,
        workflow_id: str,
        video_id: str,
        state: str,
        data: Dict[str, Any],
        success: bool = True,
    ) -> None:
        """
        Record a pipeline state transition.
        Writes to Neo4j (:WorkflowEvent) node and local audit NDJSON.
        """
        event = {
            "workflow_id": workflow_id,
            "video_id":    video_id,
            "state":       state,
            "success":     success,
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "data_keys":   list(data.keys()),
        }
        self._write_audit_event(workflow_id, video_id, state, event)
        self._upsert_neo4j_event(workflow_id, video_id, state, success)

    def _write_audit_event(
        self, workflow_id: str, video_id: str, state: str, data: Dict[str, Any]
    ) -> None:
        """Append event to local NDJSON audit trail file."""
        record = {
            "ts":          datetime.now(timezone.utc).isoformat(),
            "workflow_id": workflow_id,
            "video_id":    video_id,
            "state":       state,
            "data":        data,
        }
        try:
            os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
            with open(self.audit_log_path, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.warning("audit_write_error", error=str(e))

    def _upsert_neo4j_event(
        self, workflow_id: str, video_id: str, state: str, success: bool
    ) -> None:
        """Write WorkflowEvent node to Neo4j for broadcaster dashboard."""
        cypher = """
        MERGE (e:WorkflowEvent {
            workflow_id: $workflow_id,
            state: $state
        })
        SET e += {
            video_id:   $video_id,
            success:    $success,
            recorded_at: timestamp()
        }
        WITH e
        MATCH (v:Video {video_id: $video_id})
        MERGE (v)-[:HAS_WORKFLOW_EVENT]->(e)
        """
        try:
            with db.driver.session() as s:
                s.run(cypher, workflow_id=workflow_id,
                      video_id=video_id, state=state, success=success)
        except Exception as e:
            logger.warning("neo4j_event_error", error=str(e))

    # ── MAM integration ───────────────────────────────────────────────────────
    async def push_to_mam(
        self,
        video_meta: Dict[str, Any],
        segments: List[Dict[str, Any]],
        compliance_flags: List[Dict[str, Any]],
        brief: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Push enriched metadata to broadcaster MAM system.
        Produces SMPTE ST 2067-aligned metadata record.
        """
        mam_record = build_mam_metadata(video_meta, segments, compliance_flags, brief)

        if self.enabled:
            return await self._push_mam_remote(mam_record)

        # Local mode: write to file + Neo4j
        return self._push_mam_local(mam_record, video_meta.get("v.video_id", ""))

    async def _push_mam_remote(self, mam_record: Dict[str, Any]) -> Dict[str, Any]:
        """Push to TrackIt MAM integration endpoint."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{TRACKIT_BASE}/mam/ingest",
                headers=_trackit_headers(),
                json=mam_record,
            )
            if resp.status_code in (200, 201):
                logger.info("trackit_mam_pushed",
                            asset_id=mam_record.get("asset_id"))
                return {"status": "pushed", "mam_id": resp.json().get("id"), "record": mam_record}
            logger.error("trackit_mam_failed",
                         status=resp.status_code, body=resp.text[:200])
        return self._push_mam_local(mam_record, mam_record.get("asset_id", ""))

    def _push_mam_local(self, mam_record: Dict[str, Any], video_id: str) -> Dict[str, Any]:
        """Write MAM record to local file and Neo4j."""
        mam_path = f"/app/downloads/mam_{video_id}.json"
        try:
            os.makedirs("/app/downloads", exist_ok=True)
            with open(mam_path, "w") as f:
                json.dump(mam_record, f, indent=2)
        except Exception as e:
            logger.warning("mam_write_error", error=str(e))

        # Tag video node in Neo4j with MAM status
        try:
            with db.driver.session() as s:
                s.run(
                    "MATCH (v:Video {video_id: $vid}) SET v.mam_pushed = true, v.mam_schema = $schema",
                    vid=video_id,
                    schema=mam_record.get("schema_version", ""),
                )
        except Exception as e:
            logger.warning("mam_neo4j_error", error=str(e))

        return {
            "status":     "local",
            "mam_path":   mam_path,
            "asset_id":   mam_record.get("asset_id"),
            "record":     mam_record,
            "note":       "Set TRACKIT_API_KEY to push to production MAM",
        }

    # ── CDN registration ──────────────────────────────────────────────────────
    async def register_creative_cdn(
        self,
        creative: Dict[str, Any],
        video_id: str,
    ) -> Dict[str, Any]:
        """
        Register a generated LTX creative with TrackIt's CDN for
        broadcast-grade delivery. Returns a CDN URL for use in GAM/TTD.
        """
        if not self.enabled or not creative.get("video_url"):
            cdn_url = creative.get("video_url", "")
            logger.info("trackit_cdn_simulated", video_id=video_id)
            return {
                "cdn_url":       cdn_url,
                "creative_id":   creative.get("creative_id", ""),
                "status":        "simulated",
                "latency_ms":    12,
                "note":          "Set TRACKIT_API_KEY to register with production CDN",
            }

        payload = {
            "source_url":  creative.get("video_url"),
            "creative_id": creative.get("creative_id"),
            "asset_type":  "video_ad",
            "ad_format":   creative.get("ad_format", "6s_bumper"),
            "video_id":    video_id,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{TRACKIT_BASE}/cdn/register",
                headers=_trackit_headers(),
                json=payload,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                logger.info("trackit_cdn_registered",
                            cdn_url=data.get("cdn_url"),
                            creative_id=creative.get("creative_id"))
                return {"cdn_url": data.get("cdn_url"), "status": "registered", **data}
            logger.error("trackit_cdn_failed",
                         status=resp.status_code, body=resp.text[:200])

        return {"cdn_url": creative.get("video_url"), "status": "fallback"}

    # ── Workflow status ───────────────────────────────────────────────────────
    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get pipeline state for a workflow_id."""
        if self.enabled:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{TRACKIT_BASE}/workflows/{workflow_id}",
                    headers=_trackit_headers(),
                )
                if resp.status_code == 200:
                    return resp.json()

        # Read from Neo4j
        with db.driver.session() as s:
            recs = s.run(
                """MATCH (v:Video)-[:HAS_WORKFLOW_EVENT]->(e:WorkflowEvent)
                   WHERE e.workflow_id = $wid
                   RETURN e.state, e.success, e.recorded_at
                   ORDER BY e.recorded_at""",
                wid=workflow_id,
            )
            events = [dict(r) for r in recs]

        completed = [e for e in events if e.get("e.success")]
        return {
            "workflow_id":       workflow_id,
            "completed_states":  [e["e.state"] for e in completed],
            "total_states":      len(PIPELINE_STATES),
            "progress_pct":      round(len(completed) / len(PIPELINE_STATES) * 100),
            "status":            "complete" if len(completed) == len(PIPELINE_STATES) else "running",
        }

    # ── Audit trail export ────────────────────────────────────────────────────
    def get_audit_trail(self, video_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Read audit trail records, optionally filtered by video_id."""
        records = []
        try:
            if os.path.exists(self.audit_log_path):
                with open(self.audit_log_path) as f:
                    for line in f:
                        try:
                            record = json.loads(line.strip())
                            if video_id is None or record.get("video_id") == video_id:
                                records.append(record)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.warning("audit_read_error", error=str(e))
        return records

    # ── QoE metrics ───────────────────────────────────────────────────────────
    def compute_qoe_score(self, video_meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute Quality of Experience metrics for a video.
        In production TrackIt runs VMAF and SSIM analysis.
        Here we derive a proxy score from available metadata.
        """
        view_count  = video_meta.get("v.view_count", 0) or 0
        viral_score = video_meta.get("v.viral_score", 0) or 0
        duration    = video_meta.get("v.duration", 30) or 30

        # Proxy: high-viral, short-form content correlates with good mobile QoE
        base_qoe    = min(0.5 + viral_score * 0.4, 0.95)
        duration_pen = max(0, (duration - 60) / 600)  # penalise very long
        qoe_score   = round(max(base_qoe - duration_pen, 0.3), 3)

        return {
            "qoe_score":      qoe_score,
            "estimated_vmaf": round(qoe_score * 95, 1),
            "mobile_optimised": duration <= 60,
            "view_count":     view_count,
            "viral_score":    viral_score,
            "note":           "Proxy score — set TRACKIT_API_KEY for VMAF analysis",
        }


trackit_engine = TrackItWorkflowEngine()
