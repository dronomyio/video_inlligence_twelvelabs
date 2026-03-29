"""
Circle/USDC + x402 micropayment layer.

Architecture:
  - Each API query (semantic search, campaign match, trend report)
    requires a small USDC payment on Circle's Arc testnet
  - AI agents (buying agents, MCP clients) pay per query automatically
  - Human users get a payment URL they can fund with testnet USDC
  - Revenue flows into the platform wallet; splits are tracked in Neo4j

x402 protocol:
  1. Client sends request → server returns HTTP 402 + payment details
  2. Client funds the payment (USDC transfer to platform wallet)
  3. Client retries with payment_id in header → server verifies → serves response
  4. Server records payment in Neo4j (:Payment) node

This is already live from MEV Shield — same architecture, new use case.
"""

import asyncio
import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from config import settings
import structlog

logger = structlog.get_logger()

# ── Circle API endpoints ──────────────────────────────────────────────────────
CIRCLE_TESTNET = "https://api-sandbox.circle.com/v1"
CIRCLE_MAINNET = "https://api.circle.com/v1"

def _circle_base() -> str:
    return CIRCLE_TESTNET if settings.circle_environment == "testnet" else CIRCLE_MAINNET

def _circle_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.circle_api_key}",
        "Content-Type": "application/json",
    }

# ── x402 payment tiers ────────────────────────────────────────────────────────
PAYMENT_TIERS = {
    "semantic_search":    settings.x402_price_per_query,
    "top_hooks":          settings.x402_price_per_query,
    "ad_breaks":          settings.x402_price_per_query,
    "compliance_flags":   settings.x402_price_per_query,
    "campaign_match":     settings.x402_price_campaign_match,
    "ontology_infer":     settings.x402_price_campaign_match,
    "trend_detect":       settings.x402_price_trend_report,
    "brief_lookup":       settings.x402_price_per_query * 0.5,
}


# ─────────────────────────────────────────────────────────────────────────────
# Circle Wallet Service
# ─────────────────────────────────────────────────────────────────────────────

class CircleWalletService:
    """
    Manages the platform treasury wallet on Circle Arc testnet.
    Receives USDC payments from AI agents and human users.
    """

    def __init__(self):
        self.wallet_id = settings.circle_wallet_id
        self.enabled = bool(settings.circle_api_key and settings.circle_wallet_id)

    async def get_wallet_balance(self) -> Dict[str, Any]:
        """Check USDC balance in the platform wallet."""
        if not self.enabled:
            return self._sim_balance()

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{_circle_base()}/wallets/{self.wallet_id}",
                headers=_circle_headers(),
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                balances = data.get("balances", [])
                usdc = next((b for b in balances if b.get("currency") == "USD"), {})
                return {
                    "wallet_id": self.wallet_id,
                    "usdc_balance": float(usdc.get("amount", 0)),
                    "environment": settings.circle_environment,
                    "status": "live",
                }
            logger.warning("circle_balance_failed", status=resp.status_code)
        return self._sim_balance()

    async def create_payment_intent(
        self,
        amount_usdc: float,
        query_type: str,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a Circle payment intent — returns the address to send USDC to.
        The AI agent or human client completes the transfer, then provides
        the transfer_id as proof of payment.
        """
        if not self.enabled:
            return self._sim_payment_intent(amount_usdc, query_type)

        idem_key = idempotency_key or str(uuid.uuid4())
        payload = {
            "idempotencyKey": idem_key,
            "amount": {"amount": f"{amount_usdc:.2f}", "currency": "USD"},
            "settlementCurrency": "USD",
            "paymentMethods": [{"type": "blockchain", "chain": "ARB"}],
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{_circle_base()}/paymentIntents",
                headers=_circle_headers(),
                json=payload,
            )
            if resp.status_code in (200, 201):
                data = resp.json().get("data", {})
                # Extract deposit address from payment methods
                methods = data.get("paymentMethods", [])
                deposit_address = None
                for m in methods:
                    addrs = m.get("address")
                    if addrs:
                        deposit_address = addrs
                        break

                intent_id = data.get("id", idem_key)
                logger.info("circle_payment_intent_created",
                            intent_id=intent_id, amount=amount_usdc)
                return {
                    "intent_id": intent_id,
                    "amount_usdc": amount_usdc,
                    "deposit_address": deposit_address,
                    "chain": "ARB",
                    "environment": settings.circle_environment,
                    "query_type": query_type,
                    "expires_at": int(time.time()) + 900,  # 15 min
                    "status": "pending",
                }
            logger.error("circle_intent_failed",
                         status=resp.status_code, body=resp.text[:200])

        return self._sim_payment_intent(amount_usdc, query_type)

    async def verify_transfer(self, transfer_id: str,
                               expected_amount: float) -> Dict[str, Any]:
        """
        Verify a USDC transfer was received in the platform wallet.
        Returns verified=True if amount matches within tolerance.
        """
        if not self.enabled:
            # In simulation mode, any transfer_id starting with "sim_" passes
            verified = transfer_id.startswith("sim_")
            return {
                "verified": verified,
                "transfer_id": transfer_id,
                "amount_received": expected_amount if verified else 0,
                "status": "simulated",
            }

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{_circle_base()}/transfers/{transfer_id}",
                headers=_circle_headers(),
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                status = data.get("status", "")
                amount_info = data.get("amount", {})
                received = float(amount_info.get("amount", 0))
                # Allow 1% tolerance for gas/rounding
                amount_ok = abs(received - expected_amount) <= expected_amount * 0.01
                dest = data.get("destination", {})
                wallet_ok = dest.get("id") == self.wallet_id

                verified = status == "complete" and amount_ok and wallet_ok
                logger.info("circle_transfer_verify",
                            transfer_id=transfer_id, verified=verified,
                            received=received, expected=expected_amount)
                return {
                    "verified": verified,
                    "transfer_id": transfer_id,
                    "amount_received": received,
                    "status": status,
                }
        return {"verified": False, "transfer_id": transfer_id,
                "status": "verification_failed"}

    async def get_transaction_history(self, limit: int = 20) -> Dict[str, Any]:
        """Recent USDC inflows to the platform wallet."""
        if not self.enabled:
            return self._sim_history()

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{_circle_base()}/transfers",
                headers=_circle_headers(),
                params={"walletId": self.wallet_id,
                        "pageSize": limit, "direction": "credit"},
            )
            if resp.status_code == 200:
                txns = resp.json().get("data", [])
                return {
                    "transactions": txns,
                    "count": len(txns),
                    "wallet_id": self.wallet_id,
                }
        return self._sim_history()

    # ── Simulations ───────────────────────────────────────────────────────────
    def _sim_balance(self) -> Dict[str, Any]:
        return {
            "wallet_id": self.wallet_id or "sim_wallet_viralIntel",
            "usdc_balance": 247.35,
            "environment": "testnet_simulated",
            "status": "simulated",
            "note": "Set CIRCLE_API_KEY + CIRCLE_WALLET_ID to activate live wallet",
        }

    def _sim_payment_intent(self, amount: float, query_type: str) -> Dict[str, Any]:
        intent_id = f"sim_intent_{uuid.uuid4().hex[:12]}"
        return {
            "intent_id": intent_id,
            "amount_usdc": amount,
            "deposit_address": "0xSimulatedArcTestnetAddress123456789",
            "chain": "ARB",
            "environment": "testnet_simulated",
            "query_type": query_type,
            "expires_at": int(time.time()) + 900,
            "status": "simulated",
            "note": "Transfer sim_XXXX as transfer_id to pass verification",
        }

    def _sim_history(self) -> Dict[str, Any]:
        return {
            "transactions": [
                {"id": f"sim_tx_{i}", "amount": {"amount": "0.05", "currency": "USD"},
                 "status": "complete", "createDate": "2026-03-24T10:00:00Z"}
                for i in range(5)
            ],
            "count": 5,
            "status": "simulated",
        }


# ─────────────────────────────────────────────────────────────────────────────
# x402 Payment Middleware
# ─────────────────────────────────────────────────────────────────────────────

class X402PaymentGate:
    """
    HTTP 402 payment gate for API endpoints.

    Flow:
      1. Request arrives → gate checks for X-Payment-Transfer-Id header
      2. If missing and enforcement is on → return 402 with payment details
      3. If present → verify with Circle → allow or reject

    AI agents (like MEV Shield's x402 client) handle this automatically.
    Human callers see the 402 response and fund the payment manually.
    """

    def __init__(self, circle: CircleWalletService, db):
        self.circle = circle
        self.db = db

    def _payment_required_response(
        self, query_type: str, amount: float, request: Request
    ) -> JSONResponse:
        """Standard x402 response body — machine-readable for AI agents."""
        return JSONResponse(
            status_code=402,
            content={
                "x402_version": "1.0",
                "error": "payment_required",
                "payment_required": {
                    "amount_usdc": amount,
                    "query_type": query_type,
                    "wallet_address": "0xViralIntelPlatformWallet",
                    "chain": "ARB",
                    "circle_environment": settings.circle_environment,
                    "endpoint": str(request.url),
                    "instructions": [
                        "1. Create a USDC transfer to the wallet_address above",
                        "2. Retry this request with header: X-Payment-Transfer-Id: <transfer_id>",
                        "OR: use sim_<anything> as transfer_id in testnet demo mode",
                    ],
                    "pricing": {
                        "semantic_search":   settings.x402_price_per_query,
                        "campaign_match":    settings.x402_price_campaign_match,
                        "trend_report":      settings.x402_price_trend_report,
                        "brief_lookup":      settings.x402_price_per_query * 0.5,
                    },
                },
            },
            headers={
                "X-Payment-Required": "true",
                "X-Payment-Amount-USDC": str(amount),
                "X-Payment-Chain": "ARB",
                "X-Payment-Wallet": "0xViralIntelPlatformWallet",
            },
        )

    async def gate(
        self,
        request: Request,
        query_type: str,
    ) -> Optional[JSONResponse]:
        """
        Call this at the start of any paid endpoint.
        Returns None if payment OK (proceed), or a JSONResponse (402) to return.

        Usage in endpoint:
          gate_resp = await x402_gate.gate(request, "semantic_search")
          if gate_resp:
              return gate_resp
        """
        amount = PAYMENT_TIERS.get(query_type, settings.x402_price_per_query)

        # Demo mode: no enforcement
        if not settings.x402_enforce_payment:
            return None

        transfer_id = request.headers.get("X-Payment-Transfer-Id")

        if not transfer_id:
            return self._payment_required_response(query_type, amount, request)

        # Verify the transfer with Circle
        result = await self.circle.verify_transfer(transfer_id, amount)
        if not result.get("verified"):
            logger.warning("x402_payment_unverified",
                           transfer_id=transfer_id, query_type=query_type)
            return JSONResponse(
                status_code=402,
                content={
                    "error": "payment_not_verified",
                    "transfer_id": transfer_id,
                    "details": result,
                },
            )

        # Record payment in Neo4j
        self._record_payment(
            transfer_id=transfer_id,
            query_type=query_type,
            amount=amount,
            client_ip=request.client.host if request.client else "unknown",
        )
        logger.info("x402_payment_accepted",
                    transfer_id=transfer_id, query_type=query_type, amount=amount)
        return None  # proceed

    def _record_payment(self, transfer_id: str, query_type: str,
                         amount: float, client_ip: str) -> None:
        """Write (:Payment) node to Neo4j for revenue tracking."""
        cypher = """
        MERGE (p:Payment {transfer_id: $transfer_id})
        SET p += {
            query_type:  $query_type,
            amount_usdc: $amount,
            client_ip:   $client_ip,
            chain:       'ARB',
            environment: $environment,
            paid_at:     timestamp()
        }
        """
        try:
            with self.db.driver.session() as s:
                s.run(cypher,
                      transfer_id=transfer_id,
                      query_type=query_type,
                      amount=amount,
                      client_ip=client_ip,
                      environment=settings.circle_environment)
        except Exception as e:
            logger.error("payment_record_error", error=str(e))

    def get_payment_stats(self) -> Dict[str, Any]:
        """Revenue summary from x402 payments in Neo4j."""
        q = """
        MATCH (p:Payment)
        RETURN p.query_type as query_type,
               count(p) as count,
               sum(p.amount_usdc) as total_usdc,
               avg(p.amount_usdc) as avg_usdc
        ORDER BY total_usdc DESC
        """
        try:
            with self.db.driver.session() as s:
                recs = s.run(q)
                rows = [dict(r) for r in recs]
            total = sum(r.get("total_usdc", 0) or 0 for r in rows)
            return {
                "total_revenue_usdc": round(total, 4),
                "by_query_type": rows,
                "pricing": PAYMENT_TIERS,
                "environment": settings.circle_environment,
                "enforcement": settings.x402_enforce_payment,
            }
        except Exception as e:
            logger.error("payment_stats_error", error=str(e))
            return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# MCP server tool definitions — for AI agent discovery
# ─────────────────────────────────────────────────────────────────────────────

MCP_TOOLS = [
    {
        "name":        "viral_intel_search",
        "description": "Semantic search across 500 viral short-form videos. Finds specific moments (product reveals, athletic peaks, transformation payoffs) using TwelveLabs Marengo multimodal embeddings.",
        "price_usdc":  settings.x402_price_per_query,
        "endpoint":    "POST /search/semantic",
        "input_schema": {
            "type": "object",
            "properties": {
                "query":     {"type": "string",  "description": "Natural language moment description"},
                "category":  {"type": "string",  "description": "food_cooking | product_unboxing | sports_highlights | satisfying_asmr | life_hack_tutorial"},
                "limit":     {"type": "integer", "description": "Max results (default 20)"},
            },
            "required": ["query"],
        },
    },
    {
        "name":        "viral_intel_campaign_match",
        "description": "Opus 4.6 reasons across full video inventory to produce a ranked media plan for an advertiser campaign brief. Returns top placement moments with audience match scores and per-placement reasoning.",
        "price_usdc":  settings.x402_price_campaign_match,
        "endpoint":    "POST /campaigns/match",
        "input_schema": {
            "type": "object",
            "properties": {
                "advertiser":      {"type": "string"},
                "vertical":        {"type": "string"},
                "target_audience": {"type": "string"},
                "budget_usd":      {"type": "number"},
                "max_cpm":         {"type": "number"},
                "activate_on_networks": {"type": "boolean"},
            },
            "required": ["advertiser", "vertical", "budget_usd"],
        },
    },
    {
        "name":        "viral_intel_trend_report",
        "description": "Opus 4.6 detects emerging viral content trends this week vs baseline. Returns velocity-scored trends with advertiser vertical recommendations.",
        "price_usdc":  settings.x402_price_trend_report,
        "endpoint":    "POST /trends/detect",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name":        "viral_intel_compliance_check",
        "description": "Run compliance check on a specific video. Checks alcohol, violence, brand safety, child safety rules. Returns timestamped flags with severity.",
        "price_usdc":  settings.x402_price_per_query,
        "endpoint":    "POST /compliance/check/{video_id}",
        "input_schema": {
            "type": "object",
            "properties": {"video_id": {"type": "string"}},
            "required": ["video_id"],
        },
    },
    {
        "name":        "viral_intel_top_hooks",
        "description": "Return top Hook segments ranked by viral_segment_score. These are the highest-attention opening moments across the corpus — ideal for pre-roll placement.",
        "price_usdc":  settings.x402_price_per_query * 0.5,
        "endpoint":    "GET /search/top-hooks",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "limit":    {"type": "integer"},
            },
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Instantiate (imported by main.py)
# ─────────────────────────────────────────────────────────────────────────────

circle_service = CircleWalletService()
# x402_gate is instantiated in main.py after db is available
