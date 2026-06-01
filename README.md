# Chainos

> Interactive value-chain intelligence for retail investors. Type an industry →
> see every listed company as a node (size = market cap) and the product/revenue
> flows between them as animated edges on a WebGL 3D canvas. **Data trust** is the
> non-negotiable principle: nothing reaches users that wasn't built and verified
> from disclosures by an admin + a multi-LLM agent loop.

See **`designs/Chainos_PRD_v0.0.1.md`** (product spec) and **`CLAUDE.md`** (engineering source of truth).

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

## Quickstart — one command (Docker)

Runs the **entire** stack (datastores + Engine + Studio + Terminal + Predict scheduler) and
auto-publishes the AI Data Centers seed:

```bash
docker compose up --build -d
```

Then open:

| URL | What |
|---|---|
| http://localhost:3000 | **Terminal** — the 3D value-chain canvas |
| http://localhost:3001 | **Studio** — admin data factory |
| http://localhost:8000/health | **Engine** API |

Watch the seed publish: `docker compose logs -f seed`. Stop everything: `docker compose down`
(add `-v`-equivalent `rm -rf infra/.data` to wipe data). `make docker-up` / `make docker-down`
wrap these.

> No LLM keys needed — the Engine runs deterministic/**offline** and the seed + demo still work.
> For live model calls, create a `.env` with `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY`; Compose passes
> them through. Keys stay server-side (the browser only talks to each app's same-origin proxy).

## Alternative — host dev (hot reload)

```bash
make up          # just the datastores (neo4j + postgres + redis)
make install     # pnpm install + uv sync (engine, pipeline)
make schema      # generate the Python graph-schema mirror from the TS spec
make engine      # Engine API at http://localhost:8000
make seed        # build + publish the AI Data Centers seed graph
make terminal    # Terminal at http://localhost:3000
make studio      # Studio at http://localhost:3001
```

> `docker-compose.yml` (full stack) and `infra/docker-compose.yml` (datastores only) share the same
> container names + data volume, so run one or the other — not both at once.

## Quality gates

```bash
make lint && make typecheck && make test
```
