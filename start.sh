#!/usr/bin/env bash
# ============================================================
# ViralIntel — startup and management script
# Usage: ./start.sh [up|down|restart|logs|status|test|reset]
# ============================================================
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

log()   { echo -e "${CYAN}▶${NC} $1"; }
ok()    { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; exit 1; }

# ── Preflight checks ─────────────────────────────────────────────────────────
check_env() {
  if [ ! -f .env ]; then
    warn ".env not found. Copying from .env.example..."
    cp .env.example .env
    echo ""
    echo -e "${YELLOW}ACTION REQUIRED:${NC} Edit .env and fill in your API keys:"
    echo "  TWELVELABS_API_KEY  → https://platform.twelvelabs.io"
    echo "  ANTHROPIC_API_KEY   → https://console.anthropic.com"
    echo "  CIRCLE_API_KEY      → https://console.circle.com"
    echo "  YOUTUBE_API_KEY     → https://console.cloud.google.com"
    echo ""
    echo "GAM/TTD keys are optional — services simulate when not set."
    echo "Run ./start.sh up after filling in keys."
    exit 0
  fi

  # Check required keys
  source .env 2>/dev/null || true
  MISSING=0
  for key in TWELVELABS_API_KEY ANTHROPIC_API_KEY; do
    val=$(grep "^${key}=" .env | cut -d= -f2-)
    if [ -z "$val" ] || [[ "$val" == *"your_"* ]]; then
      warn "Missing: $key (required for core features)"
      MISSING=1
    fi
  done

  for key in CIRCLE_API_KEY YOUTUBE_API_KEY; do
    val=$(grep "^${key}=" .env | cut -d= -f2-)
    if [ -z "$val" ] || [[ "$val" == *"your_"* ]]; then
      warn "Not set: $key (optional — falls back to simulation)"
    fi
  done

  if [ $MISSING -eq 1 ]; then
    echo ""
    warn "Some required keys are missing. The app will start but core AI features won't work."
    read -p "Continue anyway? [y/N] " yn
    [[ "$yn" =~ ^[Yy]$ ]] || exit 0
  fi
}

check_docker() {
  command -v docker >/dev/null 2>&1 || error "Docker not installed. Visit https://docs.docker.com/get-docker/"
  docker compose version >/dev/null 2>&1 || error "Docker Compose not available. Update Docker Desktop or install compose plugin."
  ok "Docker available"
}

# ── Commands ──────────────────────────────────────────────────────────────────
cmd_up() {
  check_env
  check_docker
  log "Starting ViralIntel stack..."
  docker compose up --build -d
  echo ""
  log "Waiting for services to be healthy..."
  sleep 5

  # Wait for backend
  for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
      break
    fi
    sleep 2
    if [ $i -eq 30 ]; then
      warn "Backend health check timed out. Check: docker compose logs backend"
    fi
  done

  echo ""
  echo -e "${BOLD}${GREEN}ViralIntel is running!${NC}"
  echo ""
  echo -e "  ${CYAN}Frontend UI${NC}        http://localhost:3000"
  echo -e "  ${CYAN}Backend API${NC}        http://localhost:8000"
  echo -e "  ${CYAN}API Docs${NC}           http://localhost:8000/docs"
  echo -e "  ${CYAN}Neo4j Browser${NC}      http://localhost:7474  (neo4j / viralpass123)"
  echo -e "  ${CYAN}MCP Manifest${NC}       http://localhost:8000/.well-known/mcp.json"
  echo ""
  echo -e "  ${YELLOW}Next step:${NC} Open the UI and click 'Run Pipeline' to start ingesting videos."
  echo ""
}

cmd_down() {
  log "Stopping ViralIntel stack..."
  docker compose down
  ok "All containers stopped"
}

cmd_restart() {
  cmd_down
  cmd_up
}

cmd_logs() {
  SERVICE=${2:-""}
  if [ -z "$SERVICE" ]; then
    docker compose logs -f --tail=100
  else
    docker compose logs -f --tail=100 "$SERVICE"
  fi
}

cmd_status() {
  echo ""
  echo -e "${BOLD}Service status:${NC}"
  docker compose ps
  echo ""
  echo -e "${BOLD}Health checks:${NC}"

  check_url() {
    if curl -sf "$1" >/dev/null 2>&1; then
      ok "$2"
    else
      warn "$2 — not responding"
    fi
  }

  check_url "http://localhost:8000/health"           "Backend API"
  check_url "http://localhost:3000"                  "Frontend UI"
  check_url "http://localhost:7474"                  "Neo4j Browser"
  check_url "http://localhost:8000/graph/stats"      "Graph stats"
  check_url "http://localhost:8000/circle/wallet"    "Circle wallet"
  check_url "http://localhost:8000/x402/pricing"     "x402 pricing"

  echo ""
  echo -e "${BOLD}Graph statistics:${NC}"
  STATS=$(curl -sf http://localhost:8000/graph/stats 2>/dev/null || echo '{}')
  echo "  $STATS" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for k,v in d.items():
        print(f'  {k}: {v}')
except:
    print('  (unavailable)')
"

  echo ""
  echo -e "${BOLD}Revenue:${NC}"
  REV=$(curl -sf http://localhost:8000/revenue 2>/dev/null || echo '{}')
  echo "$REV" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f'  Total revenue: \${d.get(\"total_revenue_usd\",0):.2f}')
    print(f'  Total deals: {d.get(\"total_deals\",0)}')
    print(f'  Total impressions: {d.get(\"total_impressions\",0):,}')
except:
    print('  (unavailable)')
"
}

cmd_test() {
  log "Running API smoke tests..."
  BASE="http://localhost:8000"
  PASS=0; FAIL=0

  test_endpoint() {
    local method=$1 url=$2 data=$3 desc=$4
    if [ "$method" = "GET" ]; then
      code=$(curl -sf -o /dev/null -w "%{http_code}" "$BASE$url" 2>/dev/null)
    else
      code=$(curl -sf -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" \
        -d "$data" "$BASE$url" 2>/dev/null)
    fi

    if [[ "$code" =~ ^(200|201|400|402)$ ]]; then
      ok "$desc (HTTP $code)"
      PASS=$((PASS+1))
    else
      warn "$desc (HTTP $code — expected 200/201/400/402)"
      FAIL=$((FAIL+1))
    fi
  }

  # Core health
  test_endpoint GET "/health" "" "Health check"
  test_endpoint GET "/graph/stats" "" "Graph stats"
  test_endpoint GET "/categories" "" "Categories"
  test_endpoint GET "/videos" "" "Video list"

  # Search track
  test_endpoint POST "/search/semantic" \
    '{"query":"cooking transformation reveal","limit":5}' \
    "Semantic search"
  test_endpoint GET "/search/top-hooks" "" "Top hooks"

  # Segmentation
  test_endpoint GET "/segment/ad-breaks" "" "Ad breaks"
  test_endpoint GET "/segment/structure-analysis" "" "Structure analysis"

  # Compliance
  test_endpoint GET "/compliance/flags" "" "Compliance flags"
  test_endpoint GET "/compliance/summary" "" "Compliance summary"

  # Briefs
  test_endpoint GET "/briefs" "" "Ad briefs"

  # Campaigns
  test_endpoint GET "/campaigns" "" "Campaigns list"

  # Circle/x402
  test_endpoint GET "/circle/wallet" "" "Circle wallet"
  test_endpoint GET "/x402/pricing" "" "x402 pricing"
  test_endpoint GET "/x402/stats" "" "x402 stats"
  test_endpoint GET "/.well-known/mcp.json" "" "MCP manifest"

  # Revenue
  test_endpoint GET "/revenue" "" "Revenue dashboard"
  test_endpoint GET "/deals" "" "Active deals"

  # Ontology
  test_endpoint GET "/ontology/schema" "" "Ontology schema"
  test_endpoint GET "/ontology/viral-formats" "" "Viral formats"

  # Pipeline
  test_endpoint GET "/pipeline/status" "" "Pipeline status"

  echo ""
  echo -e "Results: ${GREEN}$PASS passed${NC} / ${RED}$FAIL failed${NC}"
  [ $FAIL -eq 0 ] && ok "All tests passed" || warn "Some tests failed — check logs"
}

cmd_pipeline() {
  log "Starting video ingestion pipeline..."
  RESULT=$(curl -sf -X POST http://localhost:8000/pipeline/start 2>/dev/null)
  if [ $? -eq 0 ]; then
    ok "Pipeline started"
    echo "  $RESULT"
    echo ""
    log "Monitor with: ./start.sh logs worker"
    log "Or check status: curl http://localhost:8000/pipeline/status"
  else
    error "Failed to start pipeline. Is the backend running?"
  fi
}

cmd_infer() {
  log "Running Opus 4.6 ontology inference..."
  RESULT=$(curl -sf -X POST http://localhost:8000/ontology/infer 2>/dev/null)
  if [ $? -eq 0 ]; then
    ok "Ontology inference complete"
    echo "$RESULT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    patch = d.get('patch', {})
    print(f'  New node types: {len(patch.get(\"new_node_types\",[]))}')
    print(f'  New relationships: {len(patch.get(\"new_relationships\",[]))}')
    print(f'  Schema stmts applied: {d.get(\"applied\",{}).get(\"schema_stmts\",0)}')
    print(f'  Summary: {patch.get(\"reasoning_summary\",\"\")[:200]}')
except:
    print(sys.stdin.read()[:500])
" 2>/dev/null || echo "  $RESULT"
  else
    error "Inference failed. Check ANTHROPIC_API_KEY and that videos are indexed."
  fi
}

cmd_reset() {
  warn "This will delete ALL data (Neo4j, Redis, downloaded videos)."
  read -p "Are you sure? Type 'yes' to confirm: " confirm
  [ "$confirm" = "yes" ] || { log "Aborted."; exit 0; }
  log "Stopping containers..."
  docker compose down -v
  log "Removing video downloads..."
  rm -rf backend/downloads/*.mp4 backend/downloads/*.webm 2>/dev/null || true
  ok "Reset complete. Run ./start.sh up to start fresh."
}

# ── Entrypoint ────────────────────────────────────────────────────────────────
CMD=${1:-"up"}
case "$CMD" in
  up)       cmd_up ;;
  down)     cmd_down ;;
  restart)  cmd_restart ;;
  logs)     cmd_logs "$@" ;;
  status)   cmd_status ;;
  test)     cmd_test ;;
  pipeline) cmd_pipeline ;;
  infer)    cmd_infer ;;
  reset)    cmd_reset ;;
  *)
    echo -e "${BOLD}ViralIntel — startup script${NC}"
    echo ""
    echo "Usage: ./start.sh [command]"
    echo ""
    echo "Commands:"
    echo "  up        Build and start all services (default)"
    echo "  down      Stop all services"
    echo "  restart   Restart all services"
    echo "  logs      Tail all logs (./start.sh logs backend for one service)"
    echo "  status    Show service health + graph + revenue stats"
    echo "  test      Run API smoke tests"
    echo "  pipeline  Start the 500-video ingestion pipeline"
    echo "  infer     Run Opus 4.6 ontology inference"
    echo "  reset     Wipe all data and start fresh"
    ;;
esac
