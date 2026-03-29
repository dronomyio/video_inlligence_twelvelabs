from neo4j import GraphDatabase, AsyncGraphDatabase
from typing import Optional, List, Dict, Any
from config import settings
import structlog

logger = structlog.get_logger()

# ─── Ontology Schema ──────────────────────────────────────────────────────────
#
#  (:Video)       — root node, one per ingested clip
#  (:Scene)       — temporal segment within a video
#  (:Creator)     — channel / creator entity
#  (:Trend)       — sound, hashtag, or visual meme
#  (:Category)    — top-level content category
#  (:AdvertBrief) — generated advertiser placement brief
#  (:ComplianceFlag) — compliance issue detected in a scene
#
#  Relationships:
#  (Scene)-[:SEGMENT_OF]->(Video)
#  (Video)-[:CREATED_BY]->(Creator)
#  (Video)-[:TAGGED_WITH]->(Trend)
#  (Video)-[:BELONGS_TO]->(Category)
#  (Video)-[:HAS_BRIEF]->(AdvertBrief)
#  (Scene)-[:HAS_FLAG]->(ComplianceFlag)
#  (Video)-[:SIMILAR_TO {score}]->(Video)   ← cosine sim edges
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA_CYPHER = """
CREATE CONSTRAINT video_id IF NOT EXISTS FOR (v:Video) REQUIRE v.video_id IS UNIQUE;
CREATE CONSTRAINT creator_id IF NOT EXISTS FOR (c:Creator) REQUIRE c.channel_id IS UNIQUE;
CREATE CONSTRAINT trend_name IF NOT EXISTS FOR (t:Trend) REQUIRE t.name IS UNIQUE;
CREATE CONSTRAINT category_name IF NOT EXISTS FOR (cat:Category) REQUIRE cat.name IS UNIQUE;
CREATE CONSTRAINT scene_id IF NOT EXISTS FOR (s:Scene) REQUIRE s.scene_id IS UNIQUE;
CREATE CONSTRAINT deal_id IF NOT EXISTS FOR (d:AdDeal) REQUIRE d.deal_id IS UNIQUE;
CREATE CONSTRAINT campaign_id IF NOT EXISTS FOR (c:Campaign) REQUIRE c.campaign_id IS UNIQUE;
CREATE CONSTRAINT viral_format_name IF NOT EXISTS FOR (f:ViralFormat) REQUIRE f.name IS UNIQUE;
CREATE CONSTRAINT payment_transfer_id IF NOT EXISTS FOR (p:Payment) REQUIRE p.transfer_id IS UNIQUE;
CREATE CONSTRAINT creative_id IF NOT EXISTS FOR (c:Creative) REQUIRE c.creative_id IS UNIQUE;
CREATE INDEX workflow_event_id IF NOT EXISTS FOR (e:WorkflowEvent) ON (e.workflow_id);
CREATE INDEX video_category IF NOT EXISTS FOR (v:Video) ON (v.category);
CREATE INDEX video_views IF NOT EXISTS FOR (v:Video) ON (v.view_count);
CREATE INDEX video_viral_score IF NOT EXISTS FOR (v:Video) ON (v.viral_score);
CREATE INDEX scene_type IF NOT EXISTS FOR (s:Scene) ON (s.segment_type);
CREATE INDEX deal_platform IF NOT EXISTS FOR (d:AdDeal) ON (d.platform);
CREATE INDEX deal_revenue IF NOT EXISTS FOR (d:AdDeal) ON (d.revenue_usd);
"""

class Neo4jDB:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )

    def close(self):
        self.driver.close()

    def init_schema(self):
        with self.driver.session() as session:
            for stmt in SCHEMA_CYPHER.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    try:
                        session.run(stmt)
                    except Exception as e:
                        logger.warning("schema_stmt_skip", stmt=stmt[:60], error=str(e))
        logger.info("neo4j_schema_initialized")

    # ── Video Node ────────────────────────────────────────────────────────────
    def upsert_video(self, data: Dict[str, Any]) -> str:
        cypher = """
        MERGE (v:Video {video_id: $video_id})
        SET v += {
            title: $title,
            platform: $platform,
            url: $url,
            view_count: $view_count,
            like_count: $like_count,
            comment_count: $comment_count,
            share_count: $share_count,
            duration: $duration,
            category: $category,
            description: $description,
            upload_date: $upload_date,
            twelvelabs_video_id: $twelvelabs_video_id,
            viral_score: $viral_score,
            hook_strength: $hook_strength,
            watch_through_rate: $watch_through_rate,
            thumbnail_url: $thumbnail_url,
            indexed_at: timestamp()
        }
        WITH v
        MERGE (cat:Category {name: $category})
        MERGE (v)-[:BELONGS_TO]->(cat)
        RETURN v.video_id as vid
        """
        with self.driver.session() as s:
            result = s.run(cypher, **data)
            return result.single()["vid"]

    # ── Creator Node ──────────────────────────────────────────────────────────
    def upsert_creator(self, channel_id: str, channel_name: str,
                        subscriber_count: int, niche: str) -> None:
        cypher = """
        MERGE (c:Creator {channel_id: $channel_id})
        SET c += {name: $channel_name, subscriber_count: $subscriber_count, niche: $niche}
        """
        with self.driver.session() as s:
            s.run(cypher, channel_id=channel_id, channel_name=channel_name,
                  subscriber_count=subscriber_count, niche=niche)

    def link_video_creator(self, video_id: str, channel_id: str) -> None:
        cypher = """
        MATCH (v:Video {video_id: $video_id})
        MATCH (c:Creator {channel_id: $channel_id})
        MERGE (v)-[:CREATED_BY]->(c)
        """
        with self.driver.session() as s:
            s.run(cypher, video_id=video_id, channel_id=channel_id)

    # ── Trend Node ────────────────────────────────────────────────────────────
    def upsert_trend(self, name: str, trend_type: str, video_id: str) -> None:
        cypher = """
        MERGE (t:Trend {name: $name})
        SET t.type = $trend_type
        WITH t
        MATCH (v:Video {video_id: $video_id})
        MERGE (v)-[:TAGGED_WITH]->(t)
        """
        with self.driver.session() as s:
            s.run(cypher, name=name, trend_type=trend_type, video_id=video_id)

    # ── Scene Node ────────────────────────────────────────────────────────────
    def upsert_scene(self, data: Dict[str, Any]) -> None:
        cypher = """
        MERGE (s:Scene {scene_id: $scene_id})
        SET s += {
            t_start: $t_start,
            t_end: $t_end,
            segment_type: $segment_type,
            label: $label,
            confidence: $confidence,
            attention_score: $attention_score,
            viral_segment_score: $viral_segment_score,
            description: $description
        }
        WITH s
        MATCH (v:Video {video_id: $video_id})
        MERGE (s)-[:SEGMENT_OF]->(v)
        """
        with self.driver.session() as s:
            s.run(cypher, **data)

    # ── Compliance Flag ───────────────────────────────────────────────────────
    def add_compliance_flag(self, scene_id: str, rule: str,
                             severity: str, explanation: str,
                             t_start: float, t_end: float) -> None:
        cypher = """
        MATCH (s:Scene {scene_id: $scene_id})
        CREATE (f:ComplianceFlag {
            rule: $rule,
            severity: $severity,
            explanation: $explanation,
            t_start: $t_start,
            t_end: $t_end,
            flagged_at: timestamp()
        })
        CREATE (s)-[:HAS_FLAG]->(f)
        """
        with self.driver.session() as s:
            s.run(cypher, scene_id=scene_id, rule=rule, severity=severity,
                  explanation=explanation, t_start=t_start, t_end=t_end)

    # ── Advertiser Brief ──────────────────────────────────────────────────────
    def upsert_advert_brief(self, video_id: str, brief: Dict[str, Any]) -> None:
        cypher = """
        MATCH (v:Video {video_id: $video_id})
        MERGE (ab:AdvertBrief {video_id: $video_id})
        SET ab += {
            headline: $headline,
            placement_moment: $placement_moment,
            target_verticals: $target_verticals,
            estimated_cpm: $estimated_cpm,
            zeroclick_context: $zeroclick_context,
            generated_at: timestamp()
        }
        MERGE (v)-[:HAS_BRIEF]->(ab)
        """
        with self.driver.session() as s:
            s.run(cypher, video_id=video_id, **brief)

    # ── Similarity Edges ──────────────────────────────────────────────────────
    def add_similarity_edge(self, vid_a: str, vid_b: str, score: float) -> None:
        cypher = """
        MATCH (a:Video {video_id: $vid_a})
        MATCH (b:Video {video_id: $vid_b})
        MERGE (a)-[r:SIMILAR_TO]-(b)
        SET r.score = $score
        """
        with self.driver.session() as s:
            s.run(cypher, vid_a=vid_a, vid_b=vid_b, score=score)

    # ── Search Track Queries ──────────────────────────────────────────────────
    def search_by_semantic_label(self, label: str, category: Optional[str] = None,
                                  min_viral: float = 0.5, limit: int = 20) -> List[Dict]:
        base = """
        MATCH (s:Scene)-[:SEGMENT_OF]->(v:Video)
        WHERE toLower(s.label) CONTAINS toLower($label)
          AND v.viral_score >= $min_viral
        """
        if category:
            base += " AND v.category = $category"
        base += """
        RETURN v.video_id, v.title, v.url, v.view_count, v.viral_score,
               s.t_start, s.t_end, s.label, s.segment_type, s.viral_segment_score
        ORDER BY s.viral_segment_score DESC LIMIT $limit
        """
        with self.driver.session() as s:
            r = s.run(base, label=label, category=category,
                      min_viral=min_viral, limit=limit)
            return [dict(rec) for rec in r]

    def search_top_hook_moments(self, category: Optional[str] = None,
                                 limit: int = 20) -> List[Dict]:
        q = """
        MATCH (s:Scene {segment_type: 'hook'})-[:SEGMENT_OF]->(v:Video)
        WHERE s.viral_segment_score IS NOT NULL
        """
        if category:
            q += " AND v.category = $category"
        q += """
        RETURN v.video_id, v.title, v.url, v.category, v.view_count,
               v.viral_score, s.t_start, s.t_end, s.viral_segment_score,
               s.label
        ORDER BY s.viral_segment_score DESC LIMIT $limit
        """
        with self.driver.session() as s:
            r = s.run(q, category=category, limit=limit)
            return [dict(rec) for rec in r]

    def find_similar_videos(self, video_id: str, limit: int = 10) -> List[Dict]:
        q = """
        MATCH (v:Video {video_id: $video_id})-[r:SIMILAR_TO]-(other:Video)
        RETURN other.video_id, other.title, other.url, other.category,
               other.viral_score, r.score as similarity
        ORDER BY r.score DESC LIMIT $limit
        """
        with self.driver.session() as s:
            r = s.run(q, video_id=video_id, limit=limit)
            return [dict(rec) for rec in r]

    # ── Compliance Track Queries ──────────────────────────────────────────────
    def get_compliance_flags(self, severity: Optional[str] = None) -> List[Dict]:
        q = """
        MATCH (s:Scene)-[:HAS_FLAG]->(f:ComplianceFlag)
        MATCH (s)-[:SEGMENT_OF]->(v:Video)
        """
        if severity:
            q += " WHERE f.severity = $severity"
        q += """
        RETURN v.video_id, v.title, v.category, f.rule, f.severity,
               f.explanation, f.t_start, f.t_end, s.scene_id
        ORDER BY f.severity DESC, f.t_start
        """
        with self.driver.session() as s:
            r = s.run(q, severity=severity)
            return [dict(rec) for rec in r]

    # ── Stats ─────────────────────────────────────────────────────────────────
    def get_graph_stats(self) -> Dict[str, Any]:
        try:
            with self.driver.session() as s:
                return {
                    "videos":   s.run("MATCH (n:Video) RETURN count(n) as c").single()["c"],
                    "scenes":   s.run("MATCH (n:Scene) RETURN count(n) as c").single()["c"],
                    "creators": s.run("MATCH (n:Creator) RETURN count(n) as c").single()["c"],
                    "trends":   s.run("MATCH (n:Trend) RETURN count(n) as c").single()["c"],
                    "flags":    s.run("MATCH (n:ComplianceFlag) RETURN count(n) as c").single()["c"],
                    "briefs":   s.run("MATCH (n:AdvertBrief) RETURN count(n) as c").single()["c"],
                }
        except Exception as e:
            return {"videos": 0, "scenes": 0, "creators": 0, "trends": 0, "flags": 0, "briefs": 0}

    def get_videos_paginated(self, skip: int = 0, limit: int = 50,
                              category: Optional[str] = None) -> List[Dict]:
        q = """
        MATCH (v:Video)
        """
        if category:
            q += " WHERE v.category = $category"
        q += """
        OPTIONAL MATCH (v)-[:CREATED_BY]->(c:Creator)
        OPTIONAL MATCH (v)-[:HAS_BRIEF]->(ab:AdvertBrief)
        RETURN v.video_id, v.title, v.url, v.platform, v.category,
               v.view_count, v.viral_score, v.hook_strength, v.duration,
               v.thumbnail_url, c.name as creator_name, ab.headline as brief_headline
        ORDER BY v.viral_score DESC
        SKIP $skip LIMIT $limit
        """
        with self.driver.session() as s:
            r = s.run(q, skip=skip, limit=limit, category=category)
            return [dict(rec) for rec in r]

    # ── Ontology: ViralFormat nodes ───────────────────────────────────────────
    def upsert_viral_format(self, name: str, pattern_description: str,
                             avg_viral_score: float, advertiser_value: str) -> None:
        cypher = """
        MERGE (f:ViralFormat {name: $name})
        SET f += {
            pattern_description: $pattern_description,
            avg_viral_score: $avg_viral_score,
            advertiser_value: $advertiser_value,
            updated_at: timestamp()
        }
        """
        with self.driver.session() as s:
            s.run(cypher, name=name, pattern_description=pattern_description,
                  avg_viral_score=avg_viral_score, advertiser_value=advertiser_value)

    def link_video_to_format(self, video_id: str, format_name: str,
                              confidence: float) -> None:
        cypher = """
        MATCH (v:Video {video_id: $video_id})
        MATCH (f:ViralFormat {name: $format_name})
        MERGE (v)-[r:USES_FORMAT]->(f)
        SET r.confidence = $confidence
        """
        with self.driver.session() as s:
            s.run(cypher, video_id=video_id,
                  format_name=format_name, confidence=confidence)

    def apply_ontology_patch(self, patch: Dict[str, Any]) -> Dict[str, int]:
        """Apply Opus-generated ontology patch — new node types + relationships."""
        counts = {"viral_formats": 0, "schema_stmts": 0, "errors": 0}

        # 1. Upsert new ViralFormat nodes
        for nf in patch.get("new_node_types", []):
            if nf.get("label") == "ViralFormat":
                try:
                    self.upsert_viral_format(
                        name=nf.get("label", "unknown"),
                        pattern_description=nf.get("description", ""),
                        avg_viral_score=0.0,
                        advertiser_value=nf.get("advertiser_value", ""),
                    )
                    counts["viral_formats"] += 1
                except Exception as e:
                    logger.warning("viral_format_upsert_error", error=str(e))
                    counts["errors"] += 1

        # 2. Apply raw Cypher schema patch if provided
        schema_cypher = patch.get("schema_cypher_patch", "")
        if schema_cypher:
            stmts = [s.strip() for s in schema_cypher.split(";") if s.strip()
                     and not s.strip().startswith("--")]
            with self.driver.session() as session:
                for stmt in stmts:
                    try:
                        session.run(stmt)
                        counts["schema_stmts"] += 1
                    except Exception as e:
                        logger.warning("schema_patch_stmt_skip",
                                       stmt=stmt[:60], error=str(e))
                        counts["errors"] += 1

        logger.info("ontology_patch_applied", **counts)
        return counts

    def get_corpus_snapshot(self) -> Dict[str, Any]:
        """Pull graph data needed by Opus for ontology inference."""
        with self.driver.session() as s:
            # Scene labels sample
            labels = s.run(
                "MATCH (sc:Scene) RETURN sc.label as label LIMIT 500"
            )
            scene_labels = [r["label"] for r in labels if r["label"]]

            # Tag frequency
            tags = s.run(
                """MATCH (v:Video)-[:TAGGED_WITH]->(t:Trend)
                   RETURN t.name as tag, count(*) as freq
                   ORDER BY freq DESC LIMIT 200"""
            )
            tag_freq = {r["tag"]: r["freq"] for r in tags}

            # Mood/label distribution from scenes
            moods = s.run(
                """MATCH (sc:Scene) WHERE sc.description IS NOT NULL
                   RETURN sc.segment_type as mood, count(*) as cnt
                   ORDER BY cnt DESC"""
            )
            mood_dist = {r["mood"]: r["cnt"] for r in moods}

            # Top hooks for pattern analysis
            hooks = s.run(
                """MATCH (sc:Scene {segment_type: 'hook'})-[:SEGMENT_OF]->(v:Video)
                   WHERE sc.viral_segment_score > 0.7
                   RETURN v.video_id, v.category, v.viral_score,
                          sc.label, sc.viral_segment_score, sc.attention_score
                   ORDER BY sc.viral_segment_score DESC LIMIT 50"""
            )
            top_hooks = [dict(r) for r in hooks]

        current_schema = {
            "node_labels": ["Video", "Scene", "Creator", "Trend",
                            "Category", "AdvertBrief", "ComplianceFlag",
                            "AdDeal", "Campaign", "ViralFormat"],
            "relationships": ["SEGMENT_OF", "CREATED_BY", "TAGGED_WITH",
                              "BELONGS_TO", "HAS_BRIEF", "HAS_FLAG",
                              "SIMILAR_TO", "HAS_DEAL", "USES_FORMAT",
                              "ACTIVATED_VIA"],
        }
        return {
            "current_schema": current_schema,
            "scene_labels": scene_labels,
            "tag_frequency": tag_freq,
            "mood_distribution": mood_dist,
            "top_hooks": top_hooks,
        }

    # ── Campaign nodes ────────────────────────────────────────────────────────
    def upsert_campaign(self, campaign_id: str, data: Dict[str, Any]) -> None:
        cypher = """
        MERGE (c:Campaign {campaign_id: $campaign_id})
        SET c += {
            name: $name,
            advertiser: $advertiser,
            vertical: $vertical,
            target_audience: $target_audience,
            budget_usd: $budget_usd,
            max_cpm: $max_cpm,
            brand_safety_level: $brand_safety_level,
            campaign_objective: $campaign_objective,
            status: $status,
            total_estimated_reach: $total_estimated_reach,
            total_estimated_spend: $total_estimated_spend,
            weighted_audience_match: $weighted_audience_match,
            created_at: timestamp()
        }
        """
        with self.driver.session() as s:
            s.run(cypher, campaign_id=campaign_id,
                  name=data.get("name", ""),
                  advertiser=data.get("advertiser", ""),
                  vertical=data.get("vertical", ""),
                  target_audience=data.get("target_audience", ""),
                  budget_usd=data.get("budget_usd", 0),
                  max_cpm=data.get("max_cpm", 5.0),
                  brand_safety_level=data.get("brand_safety_level", "standard"),
                  campaign_objective=data.get("campaign_objective", "awareness"),
                  status="planned",
                  total_estimated_reach=data.get("total_estimated_reach", 0),
                  total_estimated_spend=data.get("total_estimated_spend", 0),
                  weighted_audience_match=data.get("weighted_audience_match", 0))

    def link_campaign_placement(self, campaign_id: str, video_id: str,
                                 rank: int, audience_match: float,
                                 estimated_spend: float) -> None:
        cypher = """
        MATCH (c:Campaign {campaign_id: $campaign_id})
        MATCH (v:Video {video_id: $video_id})
        MERGE (c)-[r:TARGETS]->(v)
        SET r.rank = $rank,
            r.audience_match = $audience_match,
            r.estimated_spend = $estimated_spend
        """
        with self.driver.session() as s:
            s.run(cypher, campaign_id=campaign_id, video_id=video_id,
                  rank=rank, audience_match=audience_match,
                  estimated_spend=estimated_spend)

    def get_campaigns(self, limit: int = 50) -> List[Dict[str, Any]]:
        q = """
        MATCH (c:Campaign)
        OPTIONAL MATCH (c)-[:TARGETS]->(v:Video)
        RETURN c.campaign_id, c.name, c.advertiser, c.vertical,
               c.budget_usd, c.max_cpm, c.status,
               c.total_estimated_reach, c.total_estimated_spend,
               c.weighted_audience_match, c.created_at,
               count(v) as placement_count
        ORDER BY c.created_at DESC LIMIT $limit
        """
        with self.driver.session() as s:
            r = s.run(q, limit=limit)
            return [dict(rec) for rec in r]

    def get_campaign_placements(self, campaign_id: str) -> List[Dict[str, Any]]:
        q = """
        MATCH (c:Campaign {campaign_id: $cid})-[r:TARGETS]->(v:Video)
        OPTIONAL MATCH (v)-[:HAS_BRIEF]->(ab:AdvertBrief)
        OPTIONAL MATCH (v)-[:HAS_DEAL]->(d:AdDeal)
        RETURN v.video_id, v.title, v.url, v.category, v.viral_score,
               v.view_count, v.thumbnail_url,
               r.rank, r.audience_match, r.estimated_spend,
               ab.placement_moment, ab.estimated_cpm, ab.zeroclick_context,
               d.deal_id, d.platform, d.impressions, d.revenue_usd
        ORDER BY r.rank
        """
        with self.driver.session() as s:
            r = s.run(q, cid=campaign_id)
            return [dict(rec) for rec in r]

    def get_revenue_dashboard(self) -> Dict[str, Any]:
        """Aggregate revenue across all deals for the dashboard."""
        q = """
        MATCH (d:AdDeal)
        RETURN d.platform as platform,
               count(d) as deals,
               sum(d.impressions) as total_impressions,
               sum(d.revenue_usd) as total_revenue,
               avg(d.win_rate) as avg_win_rate,
               avg(d.target_cpm) as avg_cpm
        ORDER BY total_revenue DESC
        """
        with self.driver.session() as s:
            recs = s.run(q)
            platforms = [dict(r) for r in recs]

        total_rev = sum(p.get("total_revenue") or 0 for p in platforms)
        total_imp = sum(p.get("total_impressions") or 0 for p in platforms)
        total_deals = sum(p.get("deals") or 0 for p in platforms)

        return {
            "total_revenue_usd": round(total_rev, 2),
            "total_impressions": total_imp,
            "total_deals": total_deals,
            "by_platform": platforms,
        }

db = Neo4jDB()
