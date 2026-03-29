"""
Ingestion service: discovers viral short-form videos via YouTube Data API
and TikTok (via yt-dlp hashtag scraping — no API key required),
downloads with yt-dlp, returns structured metadata.

Sources:
  - YouTube Shorts: YouTube Data API v3 (falls back to yt-dlp if no key)
  - TikTok: yt-dlp hashtag/search scraping of public content (no key needed)
"""
import os
import json
import asyncio
import httpx
import yt_dlp
from typing import List, Dict, Any, Optional
from pathlib import Path
from config import settings, VIDEO_CATEGORIES, TIKTOK_HASHTAGS
import structlog

logger = structlog.get_logger()

YT_SEARCH_URL  = "https://www.googleapis.com/youtube/v3/search"
YT_VIDEOS_URL  = "https://www.googleapis.com/youtube/v3/videos"
YT_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"


class VideoIngestionService:
    def __init__(self):
        self.download_dir = Path(settings.download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.api_key = settings.youtube_api_key

    # ── YouTube Search ────────────────────────────────────────────────────────
    async def search_youtube_shorts(
        self, query: str, max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """Search YouTube for Shorts matching query with >min_views."""
        if not self.api_key:
            logger.warning("no_youtube_api_key_using_yt_dlp_fallback")
            return await self._yt_dlp_search(query, max_results)

        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: search for video IDs
            params = {
                "part": "id,snippet",
                "q": f"{query} #shorts",
                "type": "video",
                "videoDuration": "short",
                "maxResults": min(max_results, 50),
                "order": "viewCount",
                "key": self.api_key,
                "relevanceLanguage": "en",
            }
            resp = await client.get(YT_SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            if not items:
                return []

            video_ids = [i["id"]["videoId"] for i in items if "videoId" in i.get("id", {})]
            if not video_ids:
                return []

            # Step 2: get statistics for each video
            stats_params = {
                "part": "statistics,snippet,contentDetails",
                "id": ",".join(video_ids),
                "key": self.api_key,
            }
            stats_resp = await client.get(YT_VIDEOS_URL, params=stats_params)
            stats_resp.raise_for_status()
            stats_data = stats_resp.json()

            results = []
            for item in stats_data.get("items", []):
                stats = item.get("statistics", {})
                snippet = item.get("snippet", {})
                view_count = int(stats.get("viewCount", 0))

                if view_count < settings.min_views:
                    continue

                results.append({
                    "video_id": item["id"],
                    "platform": "youtube",
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", "")[:500],
                    "url": f"https://www.youtube.com/shorts/{item['id']}",
                    "watch_url": f"https://www.youtube.com/watch?v={item['id']}",
                    "channel_id": snippet.get("channelId", ""),
                    "channel_title": snippet.get("channelTitle", ""),
                    "view_count": view_count,
                    "like_count": int(stats.get("likeCount", 0)),
                    "comment_count": int(stats.get("commentCount", 0)),
                    "upload_date": snippet.get("publishedAt", ""),
                    "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    "tags": snippet.get("tags", []),
                })

            logger.info("youtube_search_complete", query=query, found=len(results))
            return results

    async def _yt_dlp_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Fallback: use yt-dlp search when no API key available."""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "playlistend": max_results,
        }
        search_url = f"ytsearch{max_results}:{query} shorts"
        results = []
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_url, download=False)
                for entry in (info.get("entries") or []):
                    if not entry:
                        continue
                    view_count = entry.get("view_count") or 0
                    if view_count < settings.min_views:
                        continue
                    vid_id = entry.get("id", "")
                    results.append({
                        "video_id": vid_id,
                        "platform": "youtube",
                        "title": entry.get("title", ""),
                        "description": (entry.get("description") or "")[:500],
                        "url": f"https://www.youtube.com/shorts/{vid_id}",
                        "watch_url": f"https://www.youtube.com/watch?v={vid_id}",
                        "channel_id": entry.get("channel_id", ""),
                        "channel_title": entry.get("channel", ""),
                        "view_count": view_count,
                        "like_count": entry.get("like_count") or 0,
                        "comment_count": entry.get("comment_count") or 0,
                        "upload_date": entry.get("upload_date", ""),
                        "thumbnail_url": entry.get("thumbnail", ""),
                        "tags": entry.get("tags") or [],
                    })
        except Exception as e:
            logger.error("yt_dlp_search_error", query=query, error=str(e))
        return results

    # ── Download ──────────────────────────────────────────────────────────────
    def download_video(self, video_id: str, url: str) -> Optional[str]:
        """Download video to /app/downloads/{video_id}.mp4. Returns local path."""
        out_path = self.download_dir / f"{video_id}.mp4"
        if out_path.exists():
            logger.info("video_already_downloaded", video_id=video_id)
            return str(out_path)

        ydl_opts = {
            "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
            "outtmpl": str(self.download_dir / f"{video_id}.%(ext)s"),
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
            "max_filesize": 100 * 1024 * 1024,  # 100 MB cap
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            # find the actual file (extension may vary)
            for f in self.download_dir.glob(f"{video_id}.*"):
                logger.info("video_downloaded", path=str(f))
                return str(f)
        except Exception as e:
            logger.error("download_error", video_id=video_id, error=str(e))
        return None

    # ── Viral Score ───────────────────────────────────────────────────────────
    def compute_viral_score(self, meta: Dict[str, Any]) -> float:
        """
        Composite virality score [0–1] using engagement signals.
        Inspired by MEV Shield cliff_score formula:
          viral_score = 0.45×view_norm + 0.30×engagement_rate + 0.25×recency_norm
        """
        view_count = meta.get("view_count", 0)
        like_count = meta.get("like_count", 0)
        comment_count = meta.get("comment_count", 0)

        # Normalize views (log scale, cap at 10M)
        import math
        view_norm = min(math.log10(max(view_count, 1)) / 7.0, 1.0)

        # Engagement rate
        total_engagement = like_count + comment_count
        engagement_rate = min(total_engagement / max(view_count, 1), 0.1) * 10

        viral_score = (0.45 * view_norm) + (0.30 * engagement_rate) + 0.25
        return round(min(viral_score, 1.0), 4)

    # ── Discover All Categories ───────────────────────────────────────────────
    async def discover_videos_for_category(
        self, category_key: str, target_count: int
    ) -> List[Dict[str, Any]]:
        """
        Gather enough unique videos for a category.
        Splits between YouTube Shorts and TikTok based on TIKTOK_SPLIT setting.
        e.g. TIKTOK_SPLIT=0.40 → 40% TikTok, 60% YouTube per category.
        """
        tiktok_count  = int(target_count * settings.tiktok_split)
        youtube_count = target_count - tiktok_count

        seen_ids: set   = set()
        collected: List = []

        # ── YouTube ───────────────────────────────────────────────────────────
        if youtube_count > 0:
            cat_config = VIDEO_CATEGORIES[category_key]
            for query in cat_config["queries"]:
                if len(collected) >= youtube_count:
                    break
                needed  = youtube_count - len(collected)
                results = await self.search_youtube_shorts(
                    query, max_results=min(needed + 10, 50)
                )
                for r in results:
                    if r["video_id"] not in seen_ids and len(collected) < youtube_count:
                        seen_ids.add(r["video_id"])
                        r["category"]             = category_key
                        r["advertiser_verticals"] = cat_config["advertiser_verticals"]
                        r["viral_score"]          = self.compute_viral_score(r)
                        collected.append(r)

        # ── TikTok ────────────────────────────────────────────────────────────
        if tiktok_count > 0 and category_key in TIKTOK_HASHTAGS:
            tiktok_results = await self.search_tiktok(
                category_key, max_results=tiktok_count + 10
            )
            cat_config = VIDEO_CATEGORIES[category_key]
            for r in tiktok_results:
                if r["video_id"] not in seen_ids and \
                   len(collected) < target_count and \
                   r.get("view_count", 0) >= settings.min_views:
                    seen_ids.add(r["video_id"])
                    r["category"]             = category_key
                    r["advertiser_verticals"] = cat_config["advertiser_verticals"]
                    r["viral_score"]          = self.compute_viral_score(r)
                    collected.append(r)

        logger.info("category_discovery_done",
                    category=category_key,
                    found=len(collected),
                    target=target_count,
                    youtube=sum(1 for v in collected if v.get("platform") == "youtube"),
                    tiktok=sum(1 for v in collected if v.get("platform") == "tiktok"))
        return collected

    # ── TikTok via yt-dlp ─────────────────────────────────────────────────────
    async def search_tiktok(
        self, category_key: str, max_results: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Scrape public TikTok videos by hashtag using yt-dlp.
        No API key required — yt-dlp fetches from tiktok.com/tag/{hashtag}.
        Only returns public videos with available metadata.
        """
        hashtags = TIKTOK_HASHTAGS.get(category_key, [])
        if not hashtags:
            return []

        results: List[Dict] = []
        seen:    set        = set()

        for hashtag in hashtags:
            if len(results) >= max_results:
                break

            url = f"https://www.tiktok.com/tag/{hashtag}"
            ydl_opts = {
                "quiet":             True,
                "no_warnings":       True,
                "extract_flat":      True,          # metadata only, no download
                "playlistend":       min(max_results - len(results) + 5, 30),
                "ignoreerrors":      True,
                "socket_timeout":    15,
                "http_headers": {
                    # Mimic a browser to avoid TikTok bot detection
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Referer": "https://www.tiktok.com/",
                },
            }

            try:
                loop = asyncio.get_event_loop()

                def _scrape():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        return ydl.extract_info(url, download=False)

                info = await loop.run_in_executor(None, _scrape)

                if not info:
                    continue

                entries = info.get("entries", [])
                if not entries and info.get("id"):
                    entries = [info]   # single video result

                for entry in entries:
                    if not entry or len(results) >= max_results:
                        break

                    vid_id = entry.get("id") or entry.get("display_id")
                    if not vid_id or vid_id in seen:
                        continue

                    # Build URL — handle both short and full formats
                    webpage_url = entry.get("webpage_url") or f"https://www.tiktok.com/@{entry.get('uploader_id','')}/video/{vid_id}"

                    view_count    = int(entry.get("view_count")    or entry.get("views", 0) or 0)
                    like_count    = int(entry.get("like_count")     or entry.get("likes", 0) or 0)
                    comment_count = int(entry.get("comment_count")  or 0)
                    duration      = float(entry.get("duration")     or 30)

                    # Skip videos longer than 3 minutes (not short-form)
                    if duration > 180:
                        continue

                    seen.add(vid_id)
                    results.append({
                        "video_id":       f"tt_{vid_id}",
                        "platform":       "tiktok",
                        "title":          entry.get("title") or entry.get("description") or "",
                        "url":            webpage_url,
                        "watch_url":      webpage_url,
                        "thumbnail_url":  entry.get("thumbnail") or "",
                        "duration":       duration,
                        "view_count":     view_count,
                        "like_count":     like_count,
                        "comment_count":  comment_count,
                        "creator":        entry.get("uploader") or entry.get("creator") or "",
                        "creator_id":     entry.get("uploader_id") or "",
                        "hashtags":       [hashtag],
                        "published_at":   str(entry.get("upload_date") or ""),
                    })

                logger.info("tiktok_hashtag_scraped",
                            hashtag=hashtag, found=len(results))

            except Exception as e:
                logger.warning("tiktok_scrape_error",
                               hashtag=hashtag, error=str(e)[:120])
                continue

        logger.info("tiktok_search_done",
                    category=category_key, found=len(results))
        return results

ingestion_service = VideoIngestionService()
