# Business Case — Archive Search Platform

## Target Customer
Mid-size sports broadcaster or news network with 10–50TB of historical footage.
Typical team: 5–15 producers and archivists spending 60%+ of their time on asset search.

## The Problem (Quantified)

| Activity | Manual process | Time |
|----------|---------------|------|
| Find a specific game moment | Watch raw footage | 4–8 hours |
| License external clip | Research + negotiate | 3–5 days + $500–5K |
| Tag new archive content | Manual metadata entry | $75K–150K/FTE/year |
| Respond to clip request | Email chain + search | 2–3 days |

**Total cost for a 100-person media org: $2–4M/year in wasted search time.**

## The Solution (Quantified)

| Activity | With Archive Search | Time |
|----------|-------------------|------|
| Find a specific game moment | Natural language query | **12 seconds** |
| Find licensable internal clip | Semantic search | **45 seconds** |
| Tag new archive content | Auto-metadata via Marengo | **$0 marginal cost** |
| Respond to clip request | Self-serve portal | **< 5 minutes** |

## ROI Calculation

**For a broadcaster with 50TB archive, 10 producers:**

```
Time saved per search:     8 hours → 12 seconds  =  7h 59m saved
Searches per producer/day: 3 searches
Working days/year:         250
Total hours saved/year:    10 producers × 3 searches × 7.99h × 250 days = 59,925 hours

At $75/hour blended cost:  59,925 × $75 = $4,494,375 saved/year

Platform cost (SaaS):      $50,000/year
ROI:                       8,888% in year one
Payback period:            < 5 days
```

## Revenue Model

| Stream | Price | Target |
|--------|-------|--------|
| SaaS subscription | $2,000–10,000/month | Broadcasters, studios |
| Per-query API (x402 USDC) | $0.05/search | AI buying agents, integrations |
| Archive monetisation share | 15% of licensing deals | Rights holders |
| MAM/DAM integration | $25,000 setup + $5K/month | Enterprise |

**Year 1 target:** 10 broadcasters × $5K/month = **$600K ARR**
**Year 3 target:** 100 customers × $8K/month = **$9.6M ARR**

## Competitive Advantage

| Capability | Legacy MAM | Generic AI Search | Archive Search |
|-----------|-----------|------------------|----------------|
| Multimodal understanding | ❌ | Partial | ✅ Visual + audio + temporal |
| Natural language queries | ❌ | Basic | ✅ Full semantic |
| Timestamp precision | Manual | ❌ | ✅ Millisecond |
| Similarity search | ❌ | ❌ | ✅ "Find more like this" |
| SMPTE MAM integration | ✅ | ❌ | ✅ (via TrackIt) |
| Compliance checking | Manual | ❌ | ✅ Automated |
| Monetisation layer | ❌ | ❌ | ✅ x402 + licensing |

## Integration Path

**Week 1:** Connect existing MAM via SMPTE ST 2067 webhook (TrackIt handles this)
**Week 2:** Index first 500 hours of archive content
**Week 3:** Train producers on natural language search
**Week 4:** Go live — measure time-to-find vs baseline

## Technology Stack

- **TwelveLabs Marengo via AWS Bedrock** — multimodal video understanding
- **Neo4j** — knowledge graph for semantic relationships
- **Anthropic Opus 4.6** — archive curation and similarity reasoning
- **TrackIt** — SMPTE ST 2067 MAM integration + audit trail
- **Circle USDC x402** — micropayment API for agent-based access
