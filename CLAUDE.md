# CLAUDE.md — Chainos

> Guidance for Claude Code when working in this repository.
> Full product spec: see **`designs/Chainos_PRD_v0.0.1.md`**. This file is the engineering source of truth; when in doubt, the PRD wins on *what*, this file wins on *how*.

---

## 1. What we're building

**Chainos** is an interactive value-chain intelligence platform for **retail investors**. Given an industry (e.g. "AI Data Centers"), it renders every listed company in that industry as a **node** (circle, size = market cap) and the **product / revenue flows** between them as animated edges, in a WebGL 3D canvas. Users explore the map (depth slider, flow filters), drill into a company's divisions/products, and run a **Predict** simulation driven by real-time news.

The non-negotiable design principle is **data trust**: nothing reaches users that wasn't built and verified from disclosures/financials by an admin + a multi-LLM agent loop.

The name = value **chain** + **OS**.

### Two-Track architecture (memorize this)

```
Chainos Studio (Admin)  →  STAGING DB  --[explicit Publish]-->  PRODUCTION DB  →  Chainos Terminal (User)
   data factory             (mutable, agent works here)            (read-only snapshot)        3D canvas
```

**Hard invariants — never violate:**
1. **Terminal reads PRODUCTION only.** Never let user-facing code touch Staging or raw agent intermediates.
2. **Publish is an explicit human action.** No auto-publish. Staging → Production is a deliberate, gated sync.
3. **Every exposed number carries `source_id` + `base_date` + `next_update`.** A value missing any of these CANNOT pass the publish validation gate.
4. **LLM/API keys are server-side only.** Never ship a provider key to the browser or embed it in client bundles.
5. **`confidence` is preserved end-to-end** (`verified` / `derived` / `estimated`) and surfaced in the UI.

---

## 2. Repo layout (monorepo)

```
/apps
  /studio          # Admin back-office (Next.js)        — the data factory UI
  /terminal        # User front-end (Next.js + R3F)     — the 3D canvas
/services
  /engine          # FastAPI + LangGraph                — LLM routing, graph build, agent loop
  /pipeline        # news/disclosure ingestion + Predict momentum jobs
/packages
  /graph-schema    # shared node/edge type defs (single source of truth for the schema)
  /ui              # shared design tokens / components
/infra             # docker-compose, db init, migrations
/designs           # product specs / design docs (PRD lives here)
/ideas             # scratch space for not-yet-promoted ideas
CLAUDE.md
designs/Chainos_PRD_v0.0.1.md
```

> If the actual layout drifts, update this section in the same PR.

---

## 3. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Graph DB | **Neo4j** | primary store; depth/relationship traversal via Cypher |
| Vector DB | **Pinecone** (or pgvector) | Predict RAG: news/disclosure embeddings |
| RDBMS | **PostgreSQL** | users, billing, job state, metadata |
| Cache/Queue | **Redis** | momentum cache, job queue |
| Backend | **Python 3.11+, FastAPI, LangGraph** | agent orchestration + LLM routing |
| Frontend | **Next.js, React Three Fiber (Three.js)** | WebGL canvas, 60fps target |
| Client state | **Zustand + TanStack Query** | canvas state + server sync |

---

## 4. LLM routing (Chainos Engine)

Route by task tier. Each tier has a Google and an Anthropic option; the admin can mix & match per project. **Model IDs as of 2026-06 — verify before changing:**

| Tier | Job | Google | Anthropic |
|---|---|---|---|
| `DEEP` | industry depth reasoning, hidden 2nd–3rd-tier vendor inference, graph skeleton | `gemini-3.1-pro-preview` | `claude-opus-4-8` |
| `MEDIUM` | precise numeric extraction from disclosures (PDF/img), cross-check | `gemini-3.5-flash` | `claude-sonnet-4-6` |
| `LOW` | news parsing, sentiment scoring, JSON schema normalization | `gemini-3.1-flash-lite` | `claude-haiku-4-5` |
| `RESEARCH` | broad candidate discovery of listed companies | **Gemini Deep Research Agent** (preview) | Claude + web_search tool |

Rules:
- The router is a single module (`services/engine/llm/router.py`). All model calls go through it — no scattered SDK calls.
- Model IDs live in **config/env**, never hardcoded across files.
- **Numeric extraction (`MEDIUM`) must cite its source** and return the exact span/value it extracted, written back as `SOURCED_FROM { extracted_value, extracted_by }`. No number enters the graph without a source link.
- Prefer dual-verification for `DEEP`/`RESEARCH` (Gemini ↔ Claude) on high-stakes edges (allocation %, revenue share).
- This is an agentic, multi-step loop — model state must be passed explicitly each turn (no hidden memory).

---

## 5. Knowledge graph schema (the contract)

Defined once in `packages/graph-schema`. Backend and front-end both import from it.

**Nodes:** `Theme`, `Company`, `Division`, `Product`, `Source`
**Edges:** `HAS_DIVISION`, `PRODUCES`, `SUPPLIES`, `REVENUE_FLOW`, `INVESTS_IN`, `COMPETES_WITH`, `SOURCED_FROM`

Canonical example (Samsung supplies HBM: 20% Google, 30% Nvidia):
```
(Samsung:Company)-[:HAS_DIVISION]->(DS:Division)-[:PRODUCES]->(HBM3E:Product)
(Samsung)-[:SUPPLIES {product_ref:"HBM3E", allocation_pct:20}]->(Google:Company)
(Samsung)-[:SUPPLIES {product_ref:"HBM3E", allocation_pct:30}]->(Nvidia:Company)
# every quantitative edge:
(:SUPPLIES)-[:SOURCED_FROM {extracted_value:"...", extracted_by:"claude-sonnet-4-6"}]->(Filing_26Q1:Source)
```

Required attrs on any quantitative value: `base_date`, `next_update`, `confidence`, and a `SOURCED_FROM` link. The validation gate enforces this before Publish.

---

## 6. Frontend conventions (Terminal — performance is a feature)

- **Target 60fps with hundreds of nodes + particle flows.**
- **Never render graph nodes as DOM elements.** Use WebGL via R3F. Use **instanced meshes** for nodes, particle pools for flow, and toggle *visibility*, don't re-mount, when the depth slider / filter changes.
- Apply LOD + frustum culling beyond ~1k nodes.
- Node size binds to live market cap; animate smoothly (lerp), don't snap.
- Depth slider and Macro→Micro transitions should feel < 100ms.
- **No `localStorage`/`sessionStorage` in any artifact-style preview;** use in-memory state.
- Predict overlay (Ghost Node expansion/contraction) is a *separate visual layer* over the fixed graph — never mutate the underlying Production data client-side.

---

## 7. Data & compliance guardrails

- Surface a **"not investment advice"** disclaimer; Predict is a momentum *simulation* — label it as such. (We are not lawyers — flag licensing/regulatory questions to the team, don't invent legal conclusions.)
- **Real-time price/market-cap data needs a licensed feed.** Don't assume free real-time quotes; default to a delayed feed until licensing is confirmed.
- **Don't redistribute disclosure/report full text.** Extract numbers + link to source; keep verbatim quoting minimal.
- Keep billing/PII in Postgres, isolated from the graph; delegate payments to a PG provider.

---

## 8. Commands

> Keep this list current — Claude Code relies on it. A root `Makefile` wraps these (`make help`).

```bash
# install
pnpm install                                   # JS workspaces
cd services/engine && uv sync --extra dev      # Python deps (pipeline likewise)

# infra (neo4j, postgres+pgvector, redis)
docker compose -f infra/docker-compose.yml up -d        # or: make up

# schema: regenerate the Python mirror after editing packages/graph-schema
pnpm --filter @chainos/graph-schema gen                  # or: make schema

# dev
pnpm --filter @chainos/terminal dev                      # or: make terminal (:3000)
pnpm --filter @chainos/studio dev                        # or: make studio   (:3001)
cd services/engine && uv run uvicorn app.main:app --reload --port 8000   # or: make engine

# seed: build + publish the AI Data Centers sample graph
cd services/engine && uv run python -m app.seed.load     # or: make seed

# quality (run before declaring done)
pnpm lint && pnpm typecheck                              # JS
cd services/engine && uv run ruff check app tests && uv run mypy app
pnpm test ; cd services/engine && uv run pytest          # or: make test
```

---

## 9. Environment variables

Never commit secrets. Expected keys (document new ones here):
```
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
NEO4J_URI= / NEO4J_USER= / NEO4J_PASSWORD=
DATABASE_URL=            # Postgres
REDIS_URL=
PINECONE_API_KEY=
MARKET_DATA_API_KEY=     # licensed price/market-cap feed
LOG_LEVEL=INFO          # DEBUG = verbose agent/LLM/graph trace (also streamed to Studio console)
LOG_FORMAT=text         # text | json (structured)
# model ids (overridable)
MODEL_DEEP_ANTHROPIC=claude-opus-4-8
MODEL_MEDIUM_ANTHROPIC=claude-sonnet-4-6
MODEL_LOW_ANTHROPIC=claude-haiku-4-5
MODEL_DEEP_GOOGLE=gemini-3.1-pro-preview
MODEL_MEDIUM_GOOGLE=gemini-3.5-flash
MODEL_LOW_GOOGLE=gemini-3.1-flash-lite
```

---

## 10. Working style for Claude Code

- **Read `designs/Chainos_PRD_v0.0.1.md` before non-trivial work.** Match its terminology exactly (Studio/Terminal, Staging/Production, Need-Fact, Predict).
- Make focused changes; keep PRs scoped to one milestone slice (see PRD §11).
- When touching the schema, edit `packages/graph-schema` and propagate — don't fork type defs.
- Prefer iterative refinement over rewrites; preserve working code.
- Verify model IDs / SDK details against current Anthropic & Google docs rather than memory.
- After changes, run lint + typecheck + tests before considering a task done.

**Do**
- Keep the Two-Track separation airtight.
- Tag every number with source + base_date + next_update.
- Route all model calls through the central router.

**Don't**
- Don't expose Staging or agent intermediates to users.
- Don't auto-publish.
- Don't put API keys client-side.
- Don't render the graph with DOM nodes.

---

## 11. Glossary

| Term | Meaning |
|---|---|
| Node | a listed company (size = market cap) |
| Edge | product/revenue/investment flow between companies |
| Depth | how many vendor tiers deep the map expands (slider 1~N) |
| Need-Fact ticket | agent → admin request for missing source data |
| Staging / Production | unverified work DB / published read-only DB |
| Publish | admin-approved Staging→Production sync |
| Predict | real-time news-driven momentum simulation (paid killer feature) |
| Ghost Node | translucent expansion/contraction overlay in Predict mode |
| base_date | the as-of date of a figure (e.g. "26 Q1 filing") |
| confidence | verified / derived / estimated |

> Note: the consumer-facing Terminal UI will likely be Korean-localized; keep user-visible strings in an i18n layer, not hardcoded.
