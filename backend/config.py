from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # ── TwelveLabs ─────────────────────────────────────────────────────────────
    twelvelabs_api_key: str = ""

    # ── AWS Bedrock (primary TwelveLabs access) ───────────────────────────────
    aws_access_key_id:     str = ""
    aws_secret_access_key: str = ""
    aws_session_token:     str = ""
    aws_region:            str = "us-east-1"

    # ── Core AI ────────────────────────────────────────────────────────────────
    anthropic_api_key: str = ""
    zeroclick_api_key: str = ""
    youtube_api_key:   str = ""

    # ── Database / Queue ───────────────────────────────────────────────────────
    neo4j_uri:      str = "bolt://neo4j:7687"
    neo4j_user:     str = "neo4j"
    neo4j_password: str = "viralpass123"
    redis_url:      str = "redis://redis:6379"

    # ── Archive ingestion config ───────────────────────────────────────────────
    min_views:      int = 1000
    target_videos:  int = 500
    tiktok_split:   float = 0.0   # default 0 for archive use case (YouTube only)

    # Archive category counts (must sum to target_videos)
    sports_count:     int = 175
    news_count:       int = 125
    production_count: int = 100
    documentary_count: int = 60
    entertainment_count: int = 40

    # ── Ad Networks ────────────────────────────────────────────────────────────
    gam_network_code:  str = ""
    gam_access_token:  str = ""
    gam_refresh_token: str = ""
    gam_client_id:     str = ""
    gam_client_secret: str = ""
    gam_order_id:      str = ""
    ttd_api_key:       str = ""
    ttd_advertiser_id: str = ""
    ttd_partner_id:    str = ""
    enable_gam:        bool = False
    enable_ttd:        bool = False

    # ── Circle / USDC ──────────────────────────────────────────────────────────
    circle_api_key:       str = ""
    circle_wallet_id:     str = ""
    circle_entity_secret: str = ""
    circle_environment:   str = "testnet"

    # ── x402 pricing ───────────────────────────────────────────────────────────
    x402_price_per_query:       float = 0.05
    x402_price_campaign_match:  float = 0.50
    x402_price_trend_report:    float = 0.25
    x402_enforce_payment:       bool  = False

    # ── LTX / TrackIt ──────────────────────────────────────────────────────────
    ltx_api_key:          str = ""
    ltx_default_format:   str = "6s_bumper"
    trackit_api_key:      str = ""
    trackit_partner_id:   str = ""
    trackit_mam_endpoint: str = ""

    download_dir: str = "/app/downloads"

    class Config:
        env_file = ".env"

settings = Settings()

# TwelveLabs index name
TWELVELABS_INDEX_NAME = "archive-search-v1"

# ── Archive video categories ───────────────────────────────────────────────────
# Reframed for broadcast/sports/news archive use case
VIDEO_CATEGORIES = {
    "sports_archive": {
        "count": settings.sports_count,
        "queries": [
            "sports game highlight moment",
            "athletic competition achievement",
            "game winning celebration sports",
            "sports broadcast coverage footage",
            "athlete performance sports clip",
        ],
        "description": "Sports broadcast & game highlights",
        "advertiser_verticals": ["sports_brands", "energy_drinks", "fitness", "apparel"],
        "archive_value": "premium",
    },
    "news_broadcast": {
        "count": settings.news_count,
        "queries": [
            "news broadcast segment report",
            "journalist interview outdoor lighting",
            "breaking news coverage footage",
            "news anchor desk broadcast",
            "field reporter live broadcast",
        ],
        "description": "News broadcast & journalism content",
        "advertiser_verticals": ["finance", "insurance", "automotive", "technology"],
        "archive_value": "high",
    },
    "production_broll": {
        "count": settings.production_count,
        "queries": [
            "b-roll footage cinematic establishing shot",
            "aerial drone shot landscape wide",
            "golden hour sunset cinematic footage",
            "slow motion nature wildlife footage",
            "urban skyline timelapse city footage",
        ],
        "description": "Studio production & B-roll footage",
        "advertiser_verticals": ["travel", "real_estate", "luxury", "automotive"],
        "archive_value": "premium",
    },
    "documentary": {
        "count": settings.documentary_count,
        "queries": [
            "documentary interview talking head",
            "historical footage archival documentary",
            "nature documentary wildlife observation",
            "cultural documentary tradition ceremony",
            "science documentary experiment discovery",
        ],
        "description": "Documentary & educational content",
        "advertiser_verticals": ["education", "streaming", "publishing", "nonprofits"],
        "archive_value": "high",
    },
    "entertainment": {
        "count": settings.entertainment_count,
        "queries": [
            "entertainment performance concert live",
            "behind the scenes production filming",
            "comedy sketch entertainment clip",
            "drama emotional scene performance",
            "music video performance artist",
        ],
        "description": "Entertainment & performance content",
        "advertiser_verticals": ["streaming", "gaming", "fashion", "beauty"],
        "archive_value": "medium",
    },
}

# ── TikTok hashtags (kept for hybrid use) ─────────────────────────────────────
TIKTOK_HASHTAGS = {
    "sports_archive":    ["sportshighlight", "athlete", "sportsmoment", "basketball", "football"],
    "news_broadcast":    ["news", "breaking", "journalism", "reporter", "coverage"],
    "production_broll":  ["cinematic", "aerial", "goldenhour", "broll", "filmmaking"],
    "documentary":       ["documentary", "nature", "wildlife", "history", "educational"],
    "entertainment":     ["performance", "concert", "behindthescenes", "entertainment", "comedy"],
}

# ── Archive example queries (for UI and demo) ──────────────────────────────────
ARCHIVE_EXAMPLE_QUERIES = [
    "emotional celebration after a game-winning moment",
    "wide establishing shots of urban skylines at golden hour",
    "interview segments with outdoor natural lighting",
    "fast-paced action with quick cuts and dynamic camera movement",
    "sunset over water with birds flying",
    "crowd reaction to unexpected sports moment",
    "news anchor delivering breaking news urgently",
    "slow motion athlete in peak performance",
    "aerial shot of stadium filled with fans",
    "behind the scenes production crew filming",
]

# ── Compliance rules ───────────────────────────────────────────────────────────
COMPLIANCE_RULES = {
    "alcohol": {
        "description": "Alcohol-related content",
        "keywords": ["beer", "wine", "whiskey", "cocktail", "drinking", "drunk", "alcohol"],
        "severity": "medium",
    },
    "violence": {
        "description": "Violent or dangerous content",
        "keywords": ["fight", "blood", "weapon", "dangerous", "injury", "crash"],
        "severity": "high",
    },
    "brand_safety": {
        "description": "Brand safety concerns",
        "keywords": ["controversial", "political", "offensive", "explicit"],
        "severity": "high",
    },
    "child_safety": {
        "description": "Child safety concerns",
        "keywords": ["minor", "children unsupervised"],
        "severity": "critical",
    },
    "copyright": {
        "description": "Potential copyright / licensed content",
        "keywords": ["licensed music", "copyrighted", "trademark", "brand logo"],
        "severity": "high",
    },
}
