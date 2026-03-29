// ── Category nodes ────────────────────────────────────────────────────────────
MERGE (:Category {name: 'food_cooking',        description: 'Food and cooking transformation videos'});
MERGE (:Category {name: 'product_unboxing',    description: 'Product unboxing and reveal videos'});
MERGE (:Category {name: 'sports_highlights',   description: 'Sports highlight moments'});
MERGE (:Category {name: 'satisfying_asmr',     description: 'Oddly satisfying and ASMR content'});
MERGE (:Category {name: 'life_hack_tutorial',  description: 'Life hacks and skill tutorials'});

// ── Compliance rule nodes ─────────────────────────────────────────────────────
MERGE (:ComplianceRule {name: 'alcohol',      severity: 'medium',   description: 'Alcohol-related content'});
MERGE (:ComplianceRule {name: 'violence',     severity: 'high',     description: 'Violent or dangerous content'});
MERGE (:ComplianceRule {name: 'brand_safety', severity: 'high',     description: 'Brand safety concerns'});
MERGE (:ComplianceRule {name: 'child_safety', severity: 'critical', description: 'Child safety concerns'});

// ── Advertiser vertical nodes ─────────────────────────────────────────────────
MERGE (:AdvertiserVertical {name: 'CPG',                  description: 'Consumer packaged goods'});
MERGE (:AdvertiserVertical {name: 'kitchenware',          description: 'Kitchen tools and appliances'});
MERGE (:AdvertiserVertical {name: 'delivery_apps',        description: 'Food delivery platforms'});
MERGE (:AdvertiserVertical {name: 'ecommerce',            description: 'Online retail'});
MERGE (:AdvertiserVertical {name: 'consumer_electronics', description: 'Tech products'});
MERGE (:AdvertiserVertical {name: 'sports_brands',        description: 'Athletic apparel and gear'});
MERGE (:AdvertiserVertical {name: 'energy_drinks',        description: 'Sports and energy beverages'});
MERGE (:AdvertiserVertical {name: 'wellness',             description: 'Health and wellness brands'});
MERGE (:AdvertiserVertical {name: 'SaaS',                 description: 'Software products'});
MERGE (:AdvertiserVertical {name: 'beauty',               description: 'Beauty and personal care'});
MERGE (:AdvertiserVertical {name: 'fitness',              description: 'Fitness and athletic performance'});

// ── ViralFormat seed nodes (Opus discovers more at runtime) ───────────────────
MERGE (:ViralFormat {name: 'face_product_hook_2s',        pattern_description: 'Face + product in first 2s', avg_viral_score: 0.0, advertiser_value: 'Highest brand recall'});
MERGE (:ViralFormat {name: 'transformation_reveal',       pattern_description: 'Before/after reveal',        avg_viral_score: 0.0, advertiser_value: 'Peak attention at reveal'});
MERGE (:ViralFormat {name: 'direct_camera_address',       pattern_description: 'Speaks to camera in 1.5s',   avg_viral_score: 0.0, advertiser_value: 'High retention hook'});
MERGE (:ViralFormat {name: 'soundoff_text_overlay_reveal',pattern_description: 'Visual only + text overlay', avg_viral_score: 0.0, advertiser_value: 'Works muted - 60% mobile'});

// ── x402 pricing config ───────────────────────────────────────────────────────
MERGE (:X402Config {name: 'default', price_semantic_search: 0.05, price_campaign_match: 0.50, price_trend_report: 0.25, chain: 'ARB', environment: 'testnet', updated_at: timestamp()});

// ── Platform wallet ───────────────────────────────────────────────────────────
MERGE (:PlatformWallet {name: 'viral_intel_treasury', chain: 'ARB', currency: 'USDC', environment: 'testnet'});

// ── Creative nodes (LTX generated ad creatives) ───────────────────────────────
// (:Creative)-[:HAS_CREATIVE]->(:Video) relationship seeded at runtime

// ── WorkflowEvent nodes (TrackIt pipeline state machine) ─────────────────────
// (:WorkflowEvent)-[:HAS_WORKFLOW_EVENT]->(:Video) seeded at runtime
