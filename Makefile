.PHONY: up down restart logs status test pipeline infer reset build \
        shell-backend shell-worker neo4j-query install-dev

# ── Primary commands ──────────────────────────────────────────────────────────
up:
	./start.sh up

down:
	./start.sh down

restart:
	./start.sh restart

logs:
	./start.sh logs

status:
	./start.sh status

test:
	./start.sh test

pipeline:
	./start.sh pipeline

infer:
	./start.sh infer

reset:
	./start.sh reset

# ── Docker shortcuts ─────────────────────────────────────────────────────────
build:
	docker compose build --no-cache

shell-backend:
	docker compose exec backend bash

shell-worker:
	docker compose exec worker bash

# ── Test commands ─────────────────────────────────────────────────────────────
test-unit:
	docker compose exec backend python -m pytest tests/test_integration.py::TestServiceLogic -v

test-api:
	docker compose exec backend python -m pytest tests/test_integration.py -v -k "not TestServiceLogic"

test-all:
	docker compose exec backend python -m pytest tests/ -v

test-circle:
	docker compose exec backend python -m pytest tests/test_integration.py::TestCircleX402 -v

test-search:
	docker compose exec backend python -m pytest tests/test_integration.py::TestSearch -v

# ── Neo4j shortcuts ───────────────────────────────────────────────────────────
neo4j-query:
	@read -p "Cypher: " q; \
	docker compose exec neo4j cypher-shell -u neo4j -p viralpass123 "$$q"

neo4j-stats:
	docker compose exec neo4j cypher-shell -u neo4j -p viralpass123 \
		"MATCH (n) RETURN labels(n)[0] as label, count(n) as count ORDER BY count DESC"

neo4j-payments:
	docker compose exec neo4j cypher-shell -u neo4j -p viralpass123 \
		"MATCH (p:Payment) RETURN p.query_type, p.amount_usdc, p.paid_at ORDER BY p.paid_at DESC LIMIT 20"

neo4j-revenue:
	docker compose exec neo4j cypher-shell -u neo4j -p viralpass123 \
		"MATCH (d:AdDeal) RETURN d.platform, sum(d.revenue_usd) as total, count(d) as deals ORDER BY total DESC"

# ── API shortcuts ─────────────────────────────────────────────────────────────
api-stats:
	@curl -s http://localhost:8000/graph/stats | python3 -m json.tool

api-revenue:
	@curl -s http://localhost:8000/revenue | python3 -m json.tool

api-wallet:
	@curl -s http://localhost:8000/circle/wallet | python3 -m json.tool

api-x402:
	@curl -s http://localhost:8000/x402/stats | python3 -m json.tool

api-mcp:
	@curl -s http://localhost:8000/.well-known/mcp.json | python3 -m json.tool

api-search:
	@read -p "Query: " q; \
	curl -s -X POST http://localhost:8000/search/semantic \
		-H "Content-Type: application/json" \
		-d "{\"query\": \"$$q\", \"limit\": 5, \"use_twelvelabs\": false}" \
		| python3 -m json.tool

api-campaign:
	@curl -s -X POST http://localhost:8000/campaigns/match \
		-H "Content-Type: application/json" \
		-d '{"name":"Test","advertiser":"TestCo","vertical":"CPG","target_audience":"adults 25-44","budget_usd":5000,"max_cpm":4.5,"activate_on_networks":false}' \
		| python3 -m json.tool

# ── Dev setup ─────────────────────────────────────────────────────────────────
install-dev:
	pip install pytest pytest-asyncio httpx structlog --break-system-packages 2>/dev/null || \
	pip install pytest pytest-asyncio httpx structlog

env-check:
	@python3 -c "
import os
keys = {
    'TWELVELABS_API_KEY': 'required',
    'ANTHROPIC_API_KEY': 'required',
    'YOUTUBE_API_KEY': 'recommended',
    'CIRCLE_API_KEY': 'revenue',
    'CIRCLE_WALLET_ID': 'revenue',
    'ZEROCLICK_API_KEY': 'briefs',
    'GAM_ACCESS_TOKEN': 'ad-network',
    'TTD_API_KEY': 'ad-network',
}
print('=== .env status ===')
try:
    env = dict(line.strip().split('=',1) for line in open('.env') 
               if '=' in line and not line.startswith('#'))
except:
    print('ERROR: .env not found'); exit(1)
for k, tier in keys.items():
    v = env.get(k,'')
    status = 'OK' if (v and 'your_' not in v) else ('SIM' if tier != 'required' else 'MISSING')
    print(f'  {status:7} [{tier:11}] {k}')
"

help:
	@echo ""
	@echo "ViralIntel — make targets"
	@echo ""
	@echo "  make up            Start all services"
	@echo "  make down          Stop all services"
	@echo "  make status        Health + stats + revenue"
	@echo "  make test          API smoke tests"
	@echo "  make pipeline      Start 500-video ingestion"
	@echo "  make infer         Opus 4.6 ontology inference"
	@echo "  make env-check     Check .env key status"
	@echo ""
	@echo "  make test-all      Full pytest suite (inside Docker)"
	@echo "  make test-circle   Circle/x402 tests only"
	@echo "  make neo4j-stats   Node counts in graph"
	@echo "  make api-revenue   Revenue dashboard"
	@echo "  make api-wallet    Circle wallet balance"
	@echo "  make api-search    Interactive search query"
	@echo ""
