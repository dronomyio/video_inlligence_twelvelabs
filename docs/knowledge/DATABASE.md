# DATABASE.md — Neo4j Schema & Cypher Patterns

## Connection

```python
# In any backend file
from database import db

with db.driver.session() as s:
    result = s.run("CYPHER QUERY", param=value)
    rows = [dict(r) for r in result]
```

Config: `NEO4J_URI=bolt://neo4j:7687` (inside Docker)
Browser: `http://localhost:7474` — login: `neo4j / viralpass123`

---

## 13 Node Types

| Node | Key Properties | Created by |
|------|----------------|-----------|
| `:Video` | `video_id`, `title`, `url`, `platform`, `viral_score`, `hook_strength`, `view_count`, `category`, `duration`, `twelvelabs_video_id` | `worker.py` |
| `:Scene` | `scene_id`, `video_id`, `t_start`, `t_end`, `segment_type`, `viral_segment_score`, `attention_score`, `confidence` | `worker.py` after Pegasus |
| `:Creator` | `creator_id`, `name`, `platform`, `subscriber_count`, `niche`, `velocity_score` | `worker.py` |
| `:Trend` | `name`, `frequency`, `velocity`, `trend_type` | `worker.py` |
| `:Category` | `name`, `description` | `seed.cypher` |
| `:AdvertBrief` | `headline`, `placement_moment`, `target_verticals`, `estimated_cpm`, `zeroclick_context` | `worker.py` + ZeroClick |
| `:ComplianceFlag` | `rule`, `severity`, `t_start`, `t_end`, `explanation` | `worker.py` + Pegasus |
| `:Campaign` | `campaign_id`, `advertiser`, `budget_usd`, `match_score`, `total_estimated_reach` | `main.py` /campaigns/match |
| `:AdDeal` | `deal_id`, `platform`, `impressions`, `revenue_usd`, `status` | `adnetwork_service.py` |
| `:ViralFormat` | `name`, `pattern_description`, `avg_viral_score`, `advertiser_value` | `opus_service.py` inference |
| `:Payment` | `transfer_id`, `query_type`, `amount_usdc`, `chain`, `environment`, `paid_at` | `circle_x402_service.py` |
| `:Creative` | `creative_id`, `video_url`, `thumbnail_url`, `ad_format`, `duration`, `status`, `provider` | `ltx_service.py` |
| `:WorkflowEvent` | `workflow_id`, `state`, `success`, `recorded_at` | `trackit_service.py` |

---

## 13 Relationships

| Relationship | From → To | Properties |
|-------------|-----------|------------|
| `SEGMENT_OF` | Scene → Video | — |
| `CREATED_BY` | Video → Creator | — |
| `TAGGED_WITH` | Video → Trend | `frequency` |
| `BELONGS_TO` | Video → Category | — |
| `HAS_BRIEF` | Video → AdvertBrief | — |
| `HAS_FLAG` | Scene → ComplianceFlag | — |
| `SIMILAR_TO` | Video → Video | `similarity_score` |
| `HAS_DEAL` | AdvertBrief → AdDeal | — |
| `USES_FORMAT` | Video → ViralFormat | `confidence` |
| `TARGETS` | Campaign → Video | `rank`, `audience_match_score` |
| `ACTIVATED_VIA` | AdDeal → Campaign | — |
| `HAS_CREATIVE` | Video → Creative | — |
| `HAS_WORKFLOW_EVENT` | Video → WorkflowEvent | — |

---

## Constraints & Indexes (from database.py init_schema)

```cypher
CREATE CONSTRAINT video_id          FOR (v:Video)         REQUIRE v.video_id IS UNIQUE;
CREATE CONSTRAINT scene_id          FOR (s:Scene)         REQUIRE s.scene_id IS UNIQUE;
CREATE CONSTRAINT creator_id        FOR (c:Creator)       REQUIRE c.creator_id IS UNIQUE;
CREATE CONSTRAINT category_name     FOR (c:Category)      REQUIRE c.name IS UNIQUE;
CREATE CONSTRAINT brief_video_id    FOR (b:AdvertBrief)   REQUIRE b.video_id IS UNIQUE;
CREATE CONSTRAINT deal_id           FOR (d:AdDeal)        REQUIRE d.deal_id IS UNIQUE;
CREATE CONSTRAINT campaign_id       FOR (c:Campaign)      REQUIRE c.campaign_id IS UNIQUE;
CREATE CONSTRAINT viral_format_name FOR (f:ViralFormat)   REQUIRE f.name IS UNIQUE;
CREATE CONSTRAINT payment_transfer  FOR (p:Payment)       REQUIRE p.transfer_id IS UNIQUE;
CREATE CONSTRAINT creative_id       FOR (c:Creative)      REQUIRE c.creative_id IS UNIQUE;
CREATE INDEX video_category         FOR (v:Video)         ON (v.category);
CREATE INDEX video_viral_score      FOR (v:Video)         ON (v.viral_score);
CREATE INDEX scene_segment_type     FOR (s:Scene)         ON (s.segment_type);
CREATE INDEX workflow_event_id      FOR (e:WorkflowEvent) ON (e.workflow_id);
```

---

## Common Cypher queries

### Get top viral videos for a category
```cypher
MATCH (v:Video)
WHERE v.category = 'food_cooking'
  AND v.viral_score > 0.7
RETURN v.video_id, v.title, v.viral_score, v.view_count
ORDER BY v.viral_score DESC
LIMIT 20
```

### Get Hook segments with no compliance flags
```cypher
MATCH (sc:Scene)-[:SEGMENT_OF]->(v:Video)
WHERE sc.segment_type = 'hook'
  AND NOT EXISTS {
    MATCH (sc)-[:HAS_FLAG]->(f:ComplianceFlag)
    WHERE f.severity IN ['high', 'critical']
  }
RETURN v.video_id, v.title, sc.t_start, sc.viral_segment_score
ORDER BY sc.viral_segment_score DESC
LIMIT 10
```

### Full video with brief and scenes
```cypher
MATCH (v:Video {video_id: $vid})
OPTIONAL MATCH (v)-[:HAS_BRIEF]->(ab:AdvertBrief)
OPTIONAL MATCH (sc:Scene)-[:SEGMENT_OF]->(v)
RETURN v, ab, collect(sc) as scenes
```

### Revenue by platform
```cypher
MATCH (d:AdDeal)
RETURN d.platform,
       count(d) as deals,
       sum(d.revenue_usd) as total_revenue,
       sum(d.impressions) as total_impressions
ORDER BY total_revenue DESC
```

### x402 payment summary
```cypher
MATCH (p:Payment)
RETURN p.query_type,
       count(p) as count,
       sum(p.amount_usdc) as total_usdc
ORDER BY total_usdc DESC
```

### Find similar videos
```cypher
MATCH (v:Video {video_id: $vid})-[r:SIMILAR_TO]->(other:Video)
RETURN other.video_id, other.title, r.similarity_score
ORDER BY r.similarity_score DESC
LIMIT 10
```

### Campaign placements
```cypher
MATCH (c:Campaign {campaign_id: $cid})-[r:TARGETS]->(v:Video)
OPTIONAL MATCH (v)-[:HAS_BRIEF]->(ab:AdvertBrief)
RETURN v.video_id, v.title, r.rank, r.audience_match_score,
       ab.estimated_cpm, ab.placement_moment
ORDER BY r.rank
```

---

## Neo4jDB methods in database.py

```python
# Write methods
db.upsert_video(video_meta)
db.upsert_creator(creator_data)
db.link_video_creator(video_id, creator_id)
db.upsert_trend(trend_name, video_id)
db.upsert_scene(scene_data)
db.add_compliance_flag(video_id, scene_id, flag_data)
db.upsert_advert_brief(video_id, brief)
db.add_similarity_edge(video_id_a, video_id_b, score)
db.upsert_viral_format(format_data)
db.link_video_to_format(video_id, format_name, confidence)
db.apply_ontology_patch(patch)
db.upsert_campaign(campaign_id, data)
db.link_campaign_placement(campaign_id, video_id, rank, score)

# Read methods
db.get_graph_stats()
db.get_videos_paginated(skip, limit, category)
db.search_by_semantic_label(label, category, limit)
db.search_top_hook_moments(category, limit)
db.find_similar_videos(video_id, limit)
db.get_compliance_flags(severity, category, limit)
db.get_corpus_snapshot()          # for Opus context
db.get_revenue_dashboard()
db.get_campaigns()
db.get_campaign_placements(campaign_id)
```

---

## Pattern: adding a new node type

```python
# 1. Add constraint in database.py init_schema()
s.run("CREATE CONSTRAINT new_type_id IF NOT EXISTS FOR (n:NewType) REQUIRE n.id IS UNIQUE")

# 2. Add upsert method in database.py
def upsert_new_thing(self, data: Dict) -> None:
    with self.driver.session() as s:
        s.run("""
            MERGE (n:NewType {id: $id})
            SET n += {name: $name, created_at: timestamp()}
        """, **data)

# 3. Add seed data in neo4j/init/seed.cypher
MERGE (:NewType {id: 'seed_1', name: 'First item'});
```
