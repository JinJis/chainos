# Chainos

> Interactive value-chain intelligence for retail investors. Type an industry →
> see every listed company as a node (size = market cap) and the product/revenue
> flows between them as animated edges on a WebGL 3D canvas. **Data trust** is the
> non-negotiable principle: nothing reaches users that wasn't built and verified
> from disclosures by an admin + a multi-LLM agent loop.

See **`Chainos_PRD_v3.md`** (product spec) and **`CLAUDE.md`** (engineering source of truth).

## Two-Track architecture

```
Chainos Studio (Admin) → STAGING DB --[explicit Publish]--> PRODUCTION DB → Chainos Terminal (User)
   data factory            (agent works here)               (read-only snapshot)     3D canvas
```

Hard invariants: Terminal reads **Production only**; Publish is an **explicit human action**; every
number carries `source_id` + `base_date` + `next_update`; **LLM keys are server-side only**;
`confidence` is preserved end-to-end.

## Layout

| Path | What |
|---|---|
| `apps/studio` | Admin back-office (Next.js) — the data factory |
| `apps/terminal` | User front-end (Next.js + R3F) — the 3D canvas |
| `services/engine` | FastAPI + LangGraph — LLM routing, graph build, agent loop, publish |
| `services/pipeline` | News/disclosure ingestion + Predict momentum |
| `packages/graph-schema` | Shared node/edge contract (TS spec → generated Python mirror) |
| `packages/ui` | Shared design tokens |
| `infra` | docker-compose (neo4j/postgres/redis), db init, seed |

## Quickstart

```bash
make up          # neo4j + postgres + redis
make install     # pnpm install + uv sync (engine, pipeline)
make schema      # generate the Python graph-schema mirror from the TS spec
make engine      # Engine API at http://localhost:8000  (GET /health)
make seed        # build + publish the AI Data Centers seed graph
make terminal    # Terminal at http://localhost:3000
make studio      # Studio at http://localhost:3001
```

No LLM keys? The Engine boots in **offline** mode (`LLM_OFFLINE=1` or simply no key set) using a
deterministic provider, so the seed graph and Terminal demo still run. Add `ANTHROPIC_API_KEY` /
`GOOGLE_API_KEY` to `.env` for live model calls.

## Quality gates

```bash
make lint && make typecheck && make test
```
