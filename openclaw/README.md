# ViralIntel — OpenClaw Entry

This directory contains three OpenClaw skills for the Viral Video Intelligence
platform (NAB 2026 Hackathon). Install all three as a bundle to give your
OpenClaw agent full knowledge of the codebase, operations, and revenue stack.

## Install

```bash
# From the project root
clawhub install ./openclaw/viral-intel-dev
clawhub install ./openclaw/viral-intel-ops
clawhub install ./openclaw/viral-intel-revenue

# Or copy the skill directories to your OpenClaw skills folder
cp -r openclaw/viral-intel-dev    ~/.openclaw/skills/
cp -r openclaw/viral-intel-ops    ~/.openclaw/skills/
cp -r openclaw/viral-intel-revenue ~/.openclaw/skills/
```

## Skills

| Skill | Activates when you say... | Covers |
|-------|--------------------------|--------|
| `viral-intel-dev` | "add endpoint", "fix backend", "Cypher query", "React page" | All 47 API endpoints, Neo4j schema + Cypher, backend services, React pages |
| `viral-intel-ops` | "run pipeline", "start Docker", "debug", "env", "ingest" | Docker commands, pipeline, env vars, health checks, errors |
| `viral-intel-revenue` | "payment", "USDC", "GAM", "TTD", "campaign", "creative" | x402/Circle, GAM/TTD deals, Opus matching, LTX creatives, MCP manifest |

## Directory structure

```
openclaw/
├── README.md                     ← this file
├── viral-intel-dev/
│   └── SKILL.md                  ← development skill
├── viral-intel-ops/
│   └── SKILL.md                  ← operations skill
└── viral-intel-revenue/
    └── SKILL.md                  ← revenue skill
```

## How skills activate

When you start an OpenClaw session in the project directory, the agent
reads all three SKILL.md files. The `description` field in each YAML
frontmatter block tells the agent when to use each skill.

Example prompts → skill triggered:
- "Add an endpoint that returns top 10 TikTok videos" → `viral-intel-dev`
- "The pipeline is stuck at tl_indexed — how do I debug?" → `viral-intel-ops`
- "Show me how to set up Circle USDC on mainnet" → `viral-intel-revenue`
- "Write a Cypher query for compliance flags by severity" → `viral-intel-dev`
- "Start the Docker services and run the pipeline" → `viral-intel-ops`
- "Activate a GAM deal for the top food video" → `viral-intel-revenue`

## Also read

`CLAUDE.md` at the project root is the master context file — it gives
a project overview and tells the agent which knowledge file to load for
any given task. If you're using Claude Code instead of OpenClaw, start
there.

## Required env vars

Set in `.env` at project root. Minimum for the agent to be useful:

```bash
TWELVELABS_API_KEY=your_key    # video indexing (required)
ANTHROPIC_API_KEY=your_key     # Opus 4.6 (required)
```

All other keys are optional — services simulate when keys are absent.
