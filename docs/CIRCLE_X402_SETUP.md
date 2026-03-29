# Circle Arc Testnet + x402 Setup Guide

## What this enables

Every API query (semantic search, campaign match, trend report) can be
monetised as a USDC micropayment on Arbitrum via Circle's Arc testnet.
AI buying agents pay automatically. Human callers see an HTTP 402 response
with a deposit address.

This is the same x402 architecture powering MEV Shield's per-query
pricing on Circle Arc. The only difference is the domain: video
intelligence instead of mempool data.

---

## Step 1: Create a Circle developer account

1. Go to https://console.circle.com
2. Sign up → verify email
3. Switch to **Testnet** mode (toggle in top-right)
4. Go to **API Keys** → Create API Key
5. Copy the key → set `CIRCLE_API_KEY` in `.env`

---

## Step 2: Create a developer-controlled wallet

Circle Arc uses "developer-controlled wallets" — you control the private
key server-side, not the user.

```bash
# In Circle console: Wallets → Developer Wallets → Create Wallet
# Select: Arbitrum (ARB) testnet
# Copy the wallet_id (format: wallet_XXXXXXXXXXXX)
```

Set in `.env`:
```
CIRCLE_WALLET_ID=wallet_XXXXXXXXXXXX
CIRCLE_ENTITY_SECRET=your_entity_secret_here
CIRCLE_ENVIRONMENT=testnet
```

The entity secret is shown once at wallet creation. Store it securely.

---

## Step 3: Fund the testnet wallet with USDC

Circle testnet USDC is free:

1. Circle console → Faucet → Request testnet USDC
2. Select your wallet → Request 100 USDC
3. Confirm balance at: `GET /circle/wallet`

---

## Step 4: Test the payment flow

### Demo mode (no real USDC, no enforcement)

The default `.env` has `X402_ENFORCE_PAYMENT=false`. In demo mode:
- All API calls work without payment
- The `/circle/wallet` and `/x402/stats` endpoints show simulated data
- Payment intents return simulated deposit addresses

This is what you demo at NAB — the full flow visible, no friction.

### Enforced mode (real USDC on testnet)

Set `X402_ENFORCE_PAYMENT=true` in `.env` and restart:

```bash
docker compose down && docker compose up -d
```

Now API calls without payment return HTTP 402:

```json
{
  "x402_version": "1.0",
  "error": "payment_required",
  "payment_required": {
    "amount_usdc": 0.05,
    "query_type": "semantic_search",
    "wallet_address": "0xYourWalletAddress",
    "chain": "ARB"
  }
}
```

### Manual payment flow (curl)

```bash
# 1. Get payment intent
curl -X POST "http://localhost:8000/circle/payment-intent?query_type=semantic_search"
# Returns: deposit_address, intent_id, amount_usdc

# 2. Send USDC to deposit_address on Arbitrum testnet
# (use Circle console or MetaMask with testnet USDC)

# 3. Verify the transfer
curl "http://localhost:8000/circle/verify/YOUR_TRANSFER_ID?query_type=semantic_search"
# Returns: {"verified": true, "amount_received": 0.05}

# 4. Call the paid endpoint with proof of payment
curl -X POST "http://localhost:8000/search/semantic" \
  -H "X-Payment-Transfer-Id: YOUR_TRANSFER_ID" \
  -H "Content-Type: application/json" \
  -d '{"query": "product reveal hands visible"}'
```

### Testnet shortcut (sim_ prefix)

Any transfer_id starting with `sim_` passes verification in testnet mode:

```bash
curl -X POST "http://localhost:8000/search/semantic" \
  -H "X-Payment-Transfer-Id: sim_anything_here" \
  -H "Content-Type: application/json" \
  -d '{"query": "cooking transformation reveal"}'
```

---

## Step 5: AI agent integration (MCP)

AI buying agents discover your API tools at:

```
GET http://localhost:8000/.well-known/mcp.json
```

This returns the MCP manifest with all tools, prices, and payment instructions.
An agent like Claude with the x402 payment plugin handles the full flow automatically:
1. Reads manifest → sees `viral_intel_search` costs $0.05 USDC
2. Creates payment intent → transfers USDC
3. Retries request with `X-Payment-Transfer-Id` header
4. Gets the search results

This is the "zero-click" AI buying agent model — the same architecture
as MEV Shield's Circle/Arc integration.

---

## Revenue model

| Query type     | Price | Margin | Opus cost | Net per query |
|----------------|-------|--------|-----------|---------------|
| Semantic search | $0.05 | 100% | $0.00 | **$0.05** |
| Top hooks       | $0.025 | 100% | $0.00 | **$0.025** |
| Campaign match  | $0.50 | ~84% | ~$0.08 | **~$0.42** |
| Trend report    | $0.25 | ~84% | ~$0.04 | **~$0.21** |

At 10,000 search queries/month + 200 campaign matches:
- Search: 10,000 × $0.05 = **$500**
- Campaign match: 200 × $0.42 = **$84**
- Total: **$584/month** from x402 alone

At 100,000 queries: **$5,840/month** — complementary to the SaaS subscription tier.

---

## Switching to mainnet

When ready for real USDC:

1. Circle console → switch to **Mainnet**
2. Create a new mainnet wallet
3. Update `.env`:
   ```
   CIRCLE_ENVIRONMENT=mainnet
   CIRCLE_API_KEY=your_mainnet_api_key
   CIRCLE_WALLET_ID=your_mainnet_wallet_id
   ```
4. Restart containers

All other code is unchanged — the `_circle_base()` function routes to
the correct endpoint based on `CIRCLE_ENVIRONMENT`.

---

## Monitoring

```bash
# Wallet balance
curl http://localhost:8000/circle/wallet

# x402 revenue by query type
curl http://localhost:8000/x402/stats

# Recent USDC inflows
curl http://localhost:8000/circle/transactions

# Neo4j: all payments
# In Neo4j browser at localhost:7474:
MATCH (p:Payment) RETURN p ORDER BY p.paid_at DESC LIMIT 20
```
