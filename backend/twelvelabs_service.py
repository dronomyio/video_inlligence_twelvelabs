"""
TwelveLabs service — AWS Bedrock mode + direct API fallback.
Set USE_BEDROCK=true + AWS credentials in .env to use Bedrock.
"""
import asyncio, json, re, time, httpx
from typing import List, Dict, Any, Optional
from config import settings, TWELVELABS_INDEX_NAME, COMPLIANCE_RULES
import structlog

logger = structlog.get_logger()
TL_BASE = "https://api.twelvelabs.io/v1.3"
HEADERS = lambda: {"x-api-key": settings.twelvelabs_api_key, "Content-Type": "application/json"}

_bedrock_client = None

def get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is None:
        try:
            import boto3
            _bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=getattr(settings, "aws_region", "us-east-1"),
                aws_access_key_id=getattr(settings, "aws_access_key_id", None),
                aws_secret_access_key=getattr(settings, "aws_secret_access_key", None),
            )
            logger.info("bedrock_client_ready")
        except Exception as e:
            logger.warning("bedrock_init_failed", error=str(e))
    return _bedrock_client


class TwelveLabsService:
    def __init__(self):
        self.index_id: Optional[str] = "69c88c3e74e8033fe643df3b"

    @property
    def use_bedrock(self):
        return (getattr(settings, "use_bedrock", False) and
                bool(getattr(settings, "aws_access_key_id", None)))

    def _bedrock_call(self, operation: str, payload: Dict) -> Dict:
        client = get_bedrock_client()
        if not client:
            raise RuntimeError("Bedrock unavailable")
        body = json.dumps({"operation": operation, **payload})
        resp = client.invoke_model(
            modelId="twelvelabs.marengo-2-7-v1",
            contentType="application/json", accept="application/json", body=body)
        return json.loads(resp["body"].read())

    async def get_or_create_index(self) -> str:
        if self.index_id:
            return self.index_id

        # New TwelveLabs API format (v1.3+)
        index_payload = {
            "name": TWELVELABS_INDEX_NAME,
            "index_name": TWELVELABS_INDEX_NAME,
            "models": [
                {"model_name": "marengo2.7", "model_options": ["visual", "audio"]},
                {"model_name": "pegasus1.2", "model_options": ["visual", "audio"]},
            ]
        }

        # Direct API
        async with httpx.AsyncClient(timeout=60) as c:
            # Check if index already exists
            r = await c.get(f"{TL_BASE}/indexes", headers=HEADERS())
            if r.status_code == 200:
                for idx in r.json().get("data", []):
                    if idx.get("name") == TWELVELABS_INDEX_NAME or idx.get("index_name") == TWELVELABS_INDEX_NAME:
                        self.index_id = idx["_id"]
                        logger.info("tl_index_found", id=self.index_id)
                        return self.index_id
            # Create new index
            r = await c.post(f"{TL_BASE}/indexes", headers=HEADERS(), json=index_payload)
            if r.status_code not in (200, 201):
                logger.warning("tl_index_create_failed", status=r.status_code, body=r.text[:200])
                # Try old format as fallback
                old_payload = {
                    "index_name": TWELVELABS_INDEX_NAME,
                    "engines": [
                        {"engine_name": "marengo2.7", "engine_options": ["visual", "audio"]},
                        {"engine_name": "pegasus1.2", "engine_options": ["visual", "audio"]},
                    ],
                    "addons": ["thumbnail"]
                }
                r = await c.post(f"{TL_BASE}/indexes", headers=HEADERS(), json=old_payload)
            r.raise_for_status()
            resp = r.json()
            self.index_id = resp.get("_id") or resp.get("id")
            logger.info("tl_index_created", id=self.index_id)
            return self.index_id

    async def index_video_from_url(self, url: str, video_id: str) -> Optional[str]:
        await self.get_or_create_index()
        if self.use_bedrock:
            try:
                res = self._bedrock_call("create_task_url",
                    {"index_id": self.index_id, "video_url": url, "language": "en"})
                tid = res.get("_id") or res.get("task_id")
                if tid:
                    return await self._poll_task(tid, video_id, bedrock=True)
            except Exception as e:
                logger.warning("bedrock_url_fallback", error=str(e))
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(f"{TL_BASE}/tasks", headers=HEADERS(),
                             json={"index_id": self.index_id, "video_url": url, "language": "en"})
            if r.status_code not in (200, 201):
                logger.error("tl_task_failed", status=r.status_code); return None
            return await self._poll_task(r.json()["_id"], video_id)

    async def index_video_from_file(self, path: str, video_id: str) -> Optional[str]:
        await self.get_or_create_index()
        async with httpx.AsyncClient(timeout=1800) as c:
            with open(path, "rb") as f:
                r = await c.post(f"{TL_BASE}/tasks",
                    headers={"x-api-key": settings.twelvelabs_api_key},
                    files={"video_file": (f"{video_id}.mp4", f, "video/mp4")},
                    data={"index_id": self.index_id, "language": "en"}, timeout=1800)
            if r.status_code not in (200, 201):
                logger.error("tl_upload_failed", status=r.status_code); return None
            return await self._poll_task(r.json()["_id"], video_id)

    async def _poll_task(self, task_id: str, video_id: str,
                          max_wait: int = 3600, bedrock: bool = False) -> Optional[str]:
        start = time.time()
        while time.time() - start < max_wait:
            try:
                if bedrock and self.use_bedrock:
                    data = self._bedrock_call("get_task", {"task_id": task_id})
                else:
                    async with httpx.AsyncClient(timeout=30) as c:
                        r = await c.get(f"{TL_BASE}/tasks/{task_id}", headers=HEADERS())
                        data = r.json() if r.status_code == 200 else {}
                status = data.get("status", "")
                if status == "ready":
                    logger.info("task_ready", video_id=video_id)
                    return data.get("video_id")
                if status in ("failed", "error"):
                    logger.error("task_failed", video_id=video_id); return None
            except Exception as e:
                logger.warning("poll_error", error=str(e))
            await asyncio.sleep(10)
        logger.error("task_timeout", video_id=video_id); return None

    async def semantic_search(self, query: str, threshold: float = 0.5,
                               limit: int = 20) -> List[Dict[str, Any]]:
        """Natural language search — 'sunset over water', 'crowd celebrating', etc."""
        await self.get_or_create_index()
        payload = {"index_id": self.index_id, "query_text": query,
                   "search_options": ["visual", "audio"],
                   "threshold": threshold, "page_limit": limit}
        if self.use_bedrock:
            try:
                return self._parse_search(self._bedrock_call("search", payload))
            except Exception as e:
                logger.warning("bedrock_search_fallback", error=str(e))
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{TL_BASE}/search",
                         headers={"x-api-key": settings.twelvelabs_api_key},
                         data={"index_id": self.index_id, "query_text": query, "page_limit": str(limit)},
                         files=[("search_options", (None, "visual")), ("search_options", (None, "audio"))])
            if r.status_code != 200:
                logger.error("search_failed", status=r.status_code); return []
            return self._parse_search(r.json())

    def _parse_search(self, data: Dict) -> List[Dict]:
        return [{"tl_video_id": d.get("video_id"), "score": d.get("score", 0),
                 "start": d.get("start", 0), "end": d.get("end", 0),
                 "thumbnail_url": d.get("thumbnail_url", ""),
                 "confidence": d.get("confidence", "")}
                for d in data.get("data", [])]

    async def find_similar(self, tl_video_id: str, limit: int = 10) -> List[Dict]:
        """'Find more clips like this' — bonus points feature."""
        await self.get_or_create_index()
        async with httpx.AsyncClient(timeout=30) as c:
            payload = {"index_id": self.index_id, "query_media_type": "video",
                       "query_media_id": tl_video_id,
                       "search_options": ["visual", "audio"],
                       "page_limit": limit}
            r = await c.post(f"{TL_BASE}/search", 
                         headers={"x-api-key": settings.twelvelabs_api_key},
                         data=payload)
            return self._parse_search(r.json()) if r.status_code == 200 else []

    async def segment_video(self, tl_video_id: str,
                             content_type: str = "auto") -> List[Dict[str, Any]]:
        """
        Segment a video into meaningful narrative units.
        content_type: sports | news | studio | documentary | auto
        Returns segments with type, timestamps, confidence, description.
        """
        segments: List[Dict[str, Any]] = []

        # ── Step 1: Pegasus chapter/highlight extraction ──────────────────────
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{TL_BASE}/summarize", headers=HEADERS(),
                             json={"video_id": tl_video_id, "types": ["chapter", "highlight"]})
            if r.status_code == 200:
                data = r.json()
                for ch in data.get("chapters", []):
                    segments.append({
                        "t_start":     ch.get("start", 0),
                        "t_end":       ch.get("end", 0),
                        "label":       ch.get("chapter_title", ""),
                        "description": ch.get("chapter_summary", ""),
                        "segment_type": "chapter",
                        "confidence":  0.85,
                        "attention_score": 0.7,
                        "source": "pegasus_chapter",
                    })

        # ── Step 2: Marengo semantic boundary detection ───────────────────────
        # Content-type specific segment taxonomy
        type_prompts = {
            "sports": """
Analyze this sports broadcast and identify structural segments. For each segment:
- segment_type: one of [teaser, opening_credits, pre_game, game_play, instant_replay,
  commercial_break_point, halftime, post_game, highlight_reel, interview, crowd_reaction,
  celebration, injury_timeout, commentary_pause, closing_credits]
- t_start, t_end: seconds (precision ±2s)
- label: max 10 words
- description: 1 sentence what happens
- confidence: 0.0-1.0
- attention_score: viewer engagement prediction 0.0-1.0
- is_ad_break_candidate: true if natural pause suitable for commercial
- boundary_quality: hard|soft|cut (hard=clear pause, soft=topic shift, cut=camera cut)
""",
            "news": """
Analyze this news broadcast and identify story segments. For each segment:
- segment_type: one of [cold_open, story_intro, field_report, anchor_desk, interview,
  b_roll_sequence, weather, sports_news, breaking_news, transition, commercial_break_point,
  closing_segment, end_credits]
- t_start, t_end: seconds (precision ±2s)
- label: topic headline (max 10 words)
- description: story summary 1 sentence
- topic: main subject
- confidence: 0.0-1.0
- attention_score: 0.0-1.0
- is_ad_break_candidate: true if natural story transition
- is_story_boundary: true if new independent story starts here
""",
            "studio": """
Analyze this studio/episodic content and identify structural segments. For each segment:
- segment_type: one of [cold_open, teaser, main_title, act_1, act_2, act_3, act_4,
  scene, montage, flashback, interview_segment, b_roll, commercial_break_point,
  tag_scene, end_credits, post_credits]
- t_start, t_end: seconds (precision ±2s)
- label: max 10 words
- description: what happens in this segment
- confidence: 0.0-1.0
- attention_score: 0.0-1.0
- is_ad_break_candidate: true if act break or natural pause
- act_number: 1-4 if applicable
""",
            "auto": """
Analyze this broadcast/archive video and identify all meaningful structural segments.
For each segment:
- segment_type: one of [opening, teaser, main_content, interview, b_roll,
  action_sequence, transition, commercial_break_point, story_boundary,
  highlight, commentary, closing, credits, ad_break_point, chapter,
  establishing_shot, celebration, crowd_reaction, breaking_moment]
- t_start, t_end: seconds (precision ±2s)
- label: max 10 words
- description: 1 sentence description
- confidence: 0.0-1.0
- attention_score: viewer engagement 0.0-1.0
- is_ad_break_candidate: true if natural pause for commercial
- boundary_quality: hard|soft|cut
"""
        }

        prompt_body = type_prompts.get(content_type, type_prompts["auto"])
        prompt = prompt_body.strip() + "\nRespond ONLY as a JSON array. No other text."

        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(f"{TL_BASE}/generate", headers=HEADERS(),
                             json={"video_id": tl_video_id, "prompt": prompt,
                                   "temperature": 0.2})
            if r.status_code == 200:
                m = re.search(r'\[.*\]', r.json().get("data", ""), re.DOTALL)
                if m:
                    try:
                        for seg in json.loads(m.group()):
                            # Composite score: weighted attention + confidence
                            seg["viral_segment_score"] = round(
                                0.6 * float(seg.get("attention_score", 0.5)) +
                                0.4 * float(seg.get("confidence", 0.5)), 4)
                            seg["content_type"] = content_type
                            seg["source"] = "marengo_semantic"
                            segments.append(seg)
                    except (json.JSONDecodeError, ValueError):
                        pass

        # ── Step 3: Deduplicate + sort by t_start ─────────────────────────────
        seen: set = set()
        deduped: List[Dict] = []
        for s in sorted(segments, key=lambda x: x.get("t_start", 0)):
            key = (round(s.get("t_start", 0)), s.get("segment_type", ""))
            if key not in seen:
                seen.add(key)
                deduped.append(s)

        return deduped

    async def check_compliance(self, tl_video_id: str,
                                rules: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        active = rules or list(COMPLIANCE_RULES.keys())
        rules_desc = "\n".join([
            f"- {k}: {v['description']} (keywords: {', '.join(v['keywords'][:4])})"
            for k, v in COMPLIANCE_RULES.items() if k in active])
        async with httpx.AsyncClient(timeout=90) as c:
            prompt = f"""Analyze for compliance issues:\n{rules_desc}
For each violation: rule, t_start, t_end, severity (low/medium/high/critical), explanation.
Return [] if none. Respond ONLY as JSON array."""
            r = await c.post(f"{TL_BASE}/generate", headers=HEADERS(),
                             json={"video_id": tl_video_id, "prompt": prompt, "temperature": 0.1})
            if r.status_code == 200:
                m = re.search(r'\[.*\]', r.json().get("data", ""), re.DOTALL)
                if m:
                    try:
                        flags = json.loads(m.group())
                        logger.info("compliance_done", flags=len(flags)); return flags
                    except json.JSONDecodeError:
                        pass
        return []

    async def extract_advertiser_context(self, tl_video_id: str) -> Dict[str, Any]:
        """Extract archive/MAM metadata for licensing and search enrichment."""
        async with httpx.AsyncClient(timeout=60) as c:
            prompt = """Analyze for archive metadata:
- setting, time_of_day, mood, key_objects (list), action_type
- audio_content (music/speech/ambient/silence)
- brand_safe (true/false), licensing_tier (free/standard/premium/exclusive)
- archive_description (one MAM-suitable sentence)
- best_placement_time (seconds), estimated_cpm_tier
Respond as JSON object."""
            r = await c.post(f"{TL_BASE}/generate", headers=HEADERS(),
                             json={"video_id": tl_video_id, "prompt": prompt, "temperature": 0.3})
            if r.status_code == 200:
                m = re.search(r'\{.*\}', r.json().get("data", ""), re.DOTALL)
                if m:
                    try: return json.loads(m.group())
                    except json.JSONDecodeError: pass
        return {}

    async def get_video_embedding(self, tl_video_id: str) -> Optional[List[float]]:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                f"{TL_BASE}/indexes/{self.index_id}/videos/{tl_video_id}", headers=HEADERS())
            return r.json().get("embedding") if r.status_code == 200 else None



    def get_mode_info(self):
        return {"mode": "direct", "index_id": self.index_id, "api_ready": bool(self.index_id)}

tl_service = TwelveLabsService()

