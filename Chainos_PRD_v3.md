# 🚀 [PRD] Chainos — AI-Driven Value Chain Intelligence

> **"Admin and AI grind the data down to a flawless set of facts; the investor consumes it as a beautiful, overwhelming visual flow."**

| Field | Value |
|---|---|
| Doc version | **v3.0.0** |
| Date | 2026-06-01 |
| Status | Draft (ready for development kickoff) |
| Target | MVP in ~12 weeks / Predict beta +6 weeks |
| Audience | PO, backend/frontend engineers, data/AI engineers, Claude Code |

---

## 0. TL;DR

Chainos is an **"interactive value-chain map of every listed company in a given industry (e.g. AI Data Centers), drawn as nodes, with the product and revenue flows between them drawn as edges."** The core differentiator is **data trust**. This is not a graph the AI hallucinated; an admin (researcher) and a multi-LLM agent loop build and re-verify every figure against disclosures, financial statements, and IB reports — and only those verified facts are exposed to users. To enforce this, the system is split, physically and logically, into the environment that *produces* data (**Chainos Studio**, Admin) and the one that *consumes* it (**Chainos Terminal**, User). A retail investor can explore the entire flow of money and product across an industry — something a brokerage HTS or trading app never shows — on a 3D canvas, and use **Predict mode** to run a real-time, news-driven simulation of who benefits and who gets hurt.

---

## 1. Naming

The service is **Chainos** — a contraction of *value **chain*** + ***OS*** (the operating system for industry value chains). Sub-products inherit the name.

| Name | Surface | One-liner |
|---|---|---|
| **Chainos** | Brand | Value-chain intelligence platform |
| **Chainos Studio** | Admin back-office | The data factory (build · verify · publish) |
| **Chainos Terminal** | User front-end | 3D exploration & prediction canvas (B2C) |
| **Chainos Engine** | Backend | LLM routing + graph builder + Predict pipeline |

---

## 2. Product overview & problem

### 2.1 Target user (primary persona)

**"A retail investor tired of chasing theme stocks."**

- Early-/mid-30s professional, 3 years into domestic + overseas equity investing. High interest in the AI semiconductor / data-center sector.
- Pain points:
  1. **"If Nvidia rallies, what rallies with it?"** — value-chain links are guessed at mentally; 2nd/3rd-tier vendors are invisible.
  2. **Fragmented information** — DART/EDGAR filings, brokerage reports, and news are scattered, with English/Japanese/Chinese language barriers.
  3. **"Which company does this news actually help?"** — it's not obvious which node a one-line headline hits, or how large the impact is.
  4. **Trust anxiety** — YouTube/blog info has unclear sources and as-of dates.

### 2.2 Why now

AI semiconductors and data centers have become a core theme across global markets, creating explosive demand to see not individual tickers but the **structure of the whole industry**. Existing tools (brokerage HTS, Bloomberg Terminal) are either (a) too expensive, (b) ticker-centric, or (c) unable to show industry structure visually.

### 2.3 Differentiation

| Existing tools | Chainos |
|---|---|
| Per-ticker search | **Industry-level node map** (whole value chain at a glance) |
| Text/table centric | **WebGL 3D flow visualization** (product & revenue *flow*) |
| Unclear sources | **Disclosure-based + as-of date / source tagging** |
| Past data only | **Predict: real-time, news-driven future simulation** |
| Mostly domestic tickers | **Global (KR · US · JP · CN · TW …) unified** |

---

## 3. Core concept & value proposition

> Type in an industry → every listed company in it surfaces as a **node** (circle, size = market cap) → companies are linked by **edges** (product/revenue flows, with particles streaming along them) → a **Depth slider** expands from 1st-tier mega-caps to Nth-tier small-caps → clicking a node **drills down to divisions/products** → the **Predict** button overlays a real-time, news-driven expansion/contraction simulation.

### Four core values
1. **Structure** — the full topology of an industry.
2. **Flow** — who sells what to whom, and how much.
3. **Trust** — every figure carries an as-of date and a source.
4. **Foresight** — a visual preview of real-time momentum.

---

## 4. System architecture (Two-Track System)

To eliminate AI hallucination at the source and lift data trust to an institutional grade, the environment that **produces** data (Admin) and the one that **consumes** it (User) are completely separated.

```
┌──────────────────────────── CHAINOS STUDIO (Admin) ─────────────────────────┐
│                                                                              │
│  Researcher(Admin)  ⇄  Multi-LLM Agent Orchestrator (LangGraph)              │
│        │                      │                                              │
│        │   ┌──────────────────┴───────────────────┐                          │
│        │   │ DEEP / MEDIUM / LOW routing           │                          │
│        │   │ Gemini Deep Research (candidate disc.)│                          │
│        │   └──────────────────┬───────────────────┘                          │
│        │                      ▼                                              │
│   Need-Fact ticket      Knowledge Graph Builder                             │
│   (Agent→Admin pull)          │                                              │
│        │                      ▼                                              │
│        └──────────────►  [ STAGING DB ]  (Neo4j staging + Postgres + Vector) │
│                               │                                              │
│                          [🚀 Publish] ── on validation pass, sync ──┐        │
└─────────────────────────────────────────────────────────────────────│──────┘
                                                                       ▼
┌──────────────────────────── CHAINOS TERMINAL (User) ────────────────────────┐
│                                                                              │
│            [ PRODUCTION DB ] (read-only snapshot) ◄───────────────┘          │
│                  │                                                           │
│    Next.js + React Three Fiber (WebGL 3D canvas, 60fps)                      │
│    Macro View → Depth Slider → Flow Filter → Node Drill-down → Predict       │
│                  ▲                                                           │
│    Live Market Feed (market cap / price)   Predict Momentum Cache (Redis)    │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Hard invariants (never violate):**
- The user reads **Production DB only**. Unverified Staging data and agent intermediates are never exposed.
- Publish is an **explicit human (Admin) action**. No auto-publish.
- Every exposed figure carries `source_id` + `base_date` + `next_update`. Missing any one → cannot Publish (validation gate).

---

## 5. Data model — knowledge graph schema

All artifacts are persisted to the graph DB. Multi-tier depth traversal is essential, so **Neo4j (graph DB)** is the primary store rather than an RDBMS.

### 5.1 Node types

| Node | Description | Key attributes |
|---|---|---|
| `Theme` | Industry/theme (e.g. AI Data Centers) | `name`, `depth_max`, `published_at`, `version` |
| `Company` | Listed company | `ticker`, `name`, `country`, `exchange`, `market_cap`(live), `sector`, `tier`(depth level), `base_date`, `next_update` |
| `Division` | Business unit (e.g. Samsung DS) | `name`, `revenue_share`(%), `parent_company` |
| `Product` | Product/service (e.g. HBM3E 12-Hi) | `name`, `category`, `unit_price`, `revenue`, `margin` |
| `Source` | Evidence | `type`(filing/IR/report/news), `url`, `publisher`, `as_of_date`, `confidence` |

### 5.2 Edge (relationship) types

| Edge | Direction | Description | Key attributes |
|---|---|---|---|
| `HAS_DIVISION` | Company→Division | company owns a division | — |
| `PRODUCES` | Division→Product | division produces a product | `capacity`, `yield` |
| `SUPPLIES` | Company→Company | supply relationship (product flow) | `product_ref`, `allocation_pct`, `direction` |
| `REVENUE_FLOW` | Company→Company | flow of revenue/money | `amount`, `currency`, `period`, `share_pct` |
| `INVESTS_IN` | Company→Company | equity stake / CAPEX | `stake_pct`, `amount` |
| `COMPETES_WITH` | Company↔Company | competition | `overlap_score` |
| `SOURCED_FROM` | (any numeric edge)→Source | **every figure links to evidence** | `extracted_value`, `extracted_by`(model id) |

> Example (req. 5): Samsung DS produces HBM → supplies 20% to Google, 30% to Nvidia
> `(Samsung)-[HAS_DIVISION]->(DS)-[PRODUCES]->(HBM3E)`
> `(Samsung)-[SUPPLIES {product_ref:HBM3E, allocation_pct:20}]->(Google)`
> `(Samsung)-[SUPPLIES {product_ref:HBM3E, allocation_pct:30}]->(Nvidia)`
> Each SUPPLIES edge links via `-[SOURCED_FROM]->(Filing 2026 Q1)`.

### 5.3 Trust & as-of rules (req. 8)

- Every quantitative attribute **must** carry `base_date` and `next_update`.
  - e.g. `base_date = "26 Q1 filing"`, `next_update = "to be reflected at 26 Q2 earnings"`.
- As-of dates differ per company, so badges are managed **per node**.
- `confidence` score: `verified` (directly cited from filing) / `derived` (agent inference) / `estimated`. Distinguished by color/icon in the user UI.

---

## 6. Workflow 1 — Chainos Studio (Admin flow)

> Reqs. 1–4. The admin steers the AI agent to "carve out" the node map. Every intermediate artifact is saved to the **Staging DB**.

### 6.1 Multi-LLM routing engine

Mix & match Google and Anthropic models per task tier, by complexity and cost efficiency. (Model IDs as of 2026-06.)

| Tier | Role | Google (option A) | Anthropic (option B) |
|---|---|---|---|
| **DEEP** (deep reasoning) | full-industry depth research, hidden 2nd/3rd-tier vendor inference, graph-skeleton draft | `gemini-3.1-pro-preview` | `claude-opus-4-8` |
| **MEDIUM** (precise extraction) | extract & cross-check key figures (revenue share %, yield) from disclosure PDFs/images, hallucination-free | `gemini-3.5-flash` | `claude-sonnet-4-6` |
| **LOW** (fast processing) | real-time news parsing, sentiment scoring, JSON schema normalization | `gemini-3.1-flash-lite` | `claude-haiku-4-5` |
| **RESEARCH** (candidate discovery) | broad discovery of listed companies in the industry | **Gemini Deep Research Agent** (preview) | Claude + web_search tool |

> Note: use the Gemini Deep Research Agent (autonomous multi-step research) as the first pass for candidate discovery, and cross-verify the precise reasoning with Claude Opus 4.8 — a dual-verification structure.

### 6.2 Step-by-step flow

**Step 1 — Project setup & model assignment**
- Admin clicks `[New Theme]` → types an industry (e.g. "AI Data Centers").
- Uploads **Additional Context**: brokerage report PDFs, industry analyses, a seed ticker list.
- Sets exploration **Depth (1~N)**. (Higher depth = expand to smaller-cap related vendors.)
- Picks per-tier model options. (e.g. "skeleton with `gemini-3.1-pro-preview`, cross-verify document parsing with `claude-sonnet-4-6`".)
- Hits `[Run Agent]`.

**Step 2 — RESEARCH + DEEP: discover constituents & list their value (reqs. 1, 2)**
- Gemini Deep Research broadly discovers **listed companies worldwide** (KR/US/JP/CN/TW …).
- The DEEP model lists out **every value each company provides** to the industry (products, talent, capital, technology).
- Renders a **draft tree** of hundreds of companies — from big tech down to lower-tier equipment makers — onto the admin canvas.
- Output: draft `Company`/`Division`/`Product` nodes + candidate `SUPPLIES` edges → **saved to Staging DB**.

**Step 3 — Need-Fact ticket: data-gap pull request (Agent ➡️ Admin) (reqs. 2, 3)**
- When the agent hits a **blank** where an authoritative figure should be, it issues a `Need-Fact` ticket to the admin.
  - e.g. *"⚠️ [Data request] Cannot infer TSMC's CoWoS packaging allocation share to Nvidia. Please upload evidence as of 26 Q1."*
- The ticket is structured: **what** (metric), **where** (target node/edge), **why** (reason).
- The admin can attach **financial statements / verified disclosures** per company to the ticket.

**Step 4 — Data injection & MEDIUM/LOW processing (Admin ➡️ Agent) (req. 3)**
- Admin uploads DART/EDGAR filing captures, IR text, etc. to the ticket.
- The **MEDIUM** model parses it immediately → extracts e.g. "allocation share 60%".
- The **LOW** model normalizes it to the Graph DB schema (JSON) → **locks** the edge data + attaches `SOURCED_FROM`.

**Step 5 — Iterative expansion (loop) (reqs. 3, 4)**
- With the injected material, the agent re-reads context, organizes **newly discovered companies/products/factors**, and **requests further material** as needed.
- Repeat Steps 3–5 up to the depth limit. Every intermediate artifact is version-controlled in Staging.

**Step 6 — Validation & publish (Publish to Terminal)**
- Validation gate: auto-check that every exposed figure carries `source_id` + `base_date` + `next_update`.
- On pass, Admin clicks `[🚀 Publish]` → **Staging data syncs to Production DB**. (Only now is it exposed to users.)

### 6.3 Studio screen spec

| Screen | Key components |
|---|---|
| Theme dashboard | theme list, version, publish status, last build time |
| Agent console | model-assignment panel, depth setting, Run/Stop, live agent log (thinking trace) |
| Graph editor | manual node/edge editing, drag, merge/split, confidence toggle |
| Need-Fact inbox | ticket list (by priority), file upload, parse-result preview/approve |
| Source manager | uploaded-material library, as-of tagging, source-verification status |
| Publish console | validation-gate report (highlight unmet items), diff preview, run deploy |

---

## 7. Workflow 2 — Chainos Terminal (User flow)

> Reqs. 5–9. The user, oblivious to the background verification grind, consumes only the overwhelming visuals and insight.

**Step 1 — Main canvas render (Macro View) (reqs. 5, 6)**
- User clicks the `[AI Data Centers]` theme.
- The whole screen turns into a dark-mode 3D space; hundreds of published nodes render smoothly via WebGL.
- **Node = company (circle)**, **node size = market cap** (linked to Live Market Feed, breathing with subtle motion).

**Step 2 — Depth slider & Flow filter (req. 6)**
- The bottom **[Depth slider 1~N]**:
  - Depth 1 → only mega nodes (Microsoft, Google, Nvidia …).
  - Higher → lower-tier vendors (e.g. ISU Petasys, Japan's Disco) fade in behind like a starfield, connected by web-like lines.
- Top **view toggle**: `[Supply-chain view]` / `[Revenue-flow view]` / `[Investment/stake view]` / `[Cost view]` / `[R&D view]`.
  - In revenue-flow view, **golden particles** stream along edges in the direction product is shipped and money returns.
- Every filter **re-composes the canvas in real time** (toggle visibility via GPU instancing, no full re-render).

**Step 3 — Node deep dive (Micro View) (req. 7)**
- User clicks the `[Samsung]` node → surrounding map dims, a **Company Drawer** opens on the right.
- Company → branches into `[DS (semiconductors)]`, `[DX (consumer)]` divisions → splits again into specific products.
- Clicking `[HBM3E 12-Hi]` → a bright **neon laser** extends only toward the customers this product flows into (Nvidia, Google) on the canvas.
- Drawer contents: division tree · per-product revenue/margin · key customers (who buys) · current price / historical return chart · market cap.
- Drawer header **trust badge**: *"📊 Base Date: 26 Q1 filing · Next update: to be reflected at 26 Q2 earnings"* (req. 8). Items with `derived`/`estimated` confidence are shown dashed / in a lighter color.

**Step 4 — ✨ Predict mode (the core paid killer feature) (req. 9)**
Overlays real-time streaming data on top of the fixed past/present graph to visually simulate value-chain change.
- Flip the top-right `[✨ Predict]` switch ON.
- **Background:** a **LOW** model (`gemini-3.1-flash-lite` or `claude-haiku-4-5`) parses 24/7 global financial news/breaking stories in real time → caches a **momentum score** per node (Redis).
- **Beneficiary nodes (expand):** a **faint blue aurora (Ghost Node)** expands around the node to ~1.2× current size with a pulse animation. **Hurt nodes (contract):** shrink in a faint red.
- **Insight tooltip (drill-down):** hover an expanding edge →
  - *"+15% short-term revenue upside momentum predicted"*
  - *"Basis: 120 news items in the last 12h on Nvidia next-gen chip thermal issues → water-cooling substitution demand (analyzed by the Haiku engine)"*
- Without reading text, the user discovers hidden beneficiaries just by watching nodes **physically expand/contract**.

> ⚠️ Predict is a **momentum simulation, not a confirmed forecast** — always labeled with a disclaimer badge. See §9 compliance.

---

## 8. Data pipeline & Predict engine detail

### 8.1 Real-time ingestion pipeline
```
news/filing sources (multilingual) → ingest (scheduler/stream) → LOW-model parse
  → entity linking (news ↔ graph node match) → sentiment & impact scoring
  → embed into Vector DB (RAG) → aggregate momentum score → Redis cache
```

### 8.2 Entity linking (the hard problem)
- Decide which node/edge a headline like "Nvidia next-gen chip thermal issue" maps to.
- Candidate approach: company-name dictionary + embedding similarity (Vector DB) + LLM adjudication. Below a confidence threshold, exclude from Predict.

### 8.3 Momentum score (example definition)
```
momentum(node) = Σ_news [ sentiment × source_weight × recency_decay × relevance ]
expansion_ratio = clamp(1.0 + k · normalize(momentum), 0.7, 1.4)   # visual size multiplier
```
- `recency_decay`: weight recent news (e.g. 12h half-life).
- Output: `node_id → {momentum, expected_delta_pct, evidence_news[], engine}`.

---

## 9. Non-functional requirements & compliance

### 9.1 Performance
- Terminal canvas: maintain **60fps** with hundreds of nodes + particle flows. → no DOM (div); **WebGL instancing** required.
- Beyond ~1,000 nodes apply LOD (Level of Detail), frustum culling, particle pooling.
- Perceived latency < 100ms for Macro→Micro transitions and the depth slider.

### 9.2 Data & legal (⚠️ must review)
- **Not investment advice (disclaimer):** Chainos is an information tool, not a solicitation or advisory. Predict results are estimated simulations. Disclaimer on every screen. (Engineering note: we are not lawyers — route licensing/regulatory questions to a qualified professional; do not invent legal conclusions.)
- **Market-data licensing:** live market cap / price may require a paid exchange/vendor **license** (delayed vs real-time). Confirm each exchange's redistribution policy.
- **Filing/report copyright:** don't redistribute brokerage reports or filing full text — extract numbers + link to source only (minimal verbatim quoting).
- **PII:** keep user billing/metadata isolated in PostgreSQL; delegate payments to a PG provider.

### 9.3 Security
- Studio (Admin) and Terminal (User) on separate auth domains. Production DB is read-only from Terminal.
- LLM API keys used **server-side only**. Never expose to the front-end.

---

## 10. Tech stack

| Layer | Choice | Reason |
|---|---|---|
| Graph DB | **Neo4j** | multi-tier depth traversal, graph queries (Cypher) |
| Vector DB | **Pinecone** (or pgvector/Qdrant) | Predict real-time news/filing embeddings (RAG) |
| RDBMS | **PostgreSQL** | users, billing, metadata, job state |
| Cache/Queue | **Redis** | momentum-score cache, job queue |
| Backend | **Python FastAPI + LangGraph** | multi-LLM routing & agent workflow control |
| LLM (multi) | **Anthropic Claude (Opus 4.8 / Sonnet 4.6 / Haiku 4.5) + Google Gemini (3.1 Pro / 3.5 Flash / 3.1 Flash-Lite + Deep Research)** | per-tier cost/perf optimum + cross-verification |
| Frontend | **Next.js + React Three Fiber (Three.js)** | WebGL 3D 60fps rendering |
| Client state | Zustand / TanStack Query | canvas state + server sync |
| Infra | Containers (Docker) + object storage (filings) | — |

---

## 11. Development roadmap (milestones)

| Stage | Est. | Deliverable |
|---|---|---|
| **M0 — Scaffolding** | 1w | monorepo, DB setup (Neo4j/PG/Redis), LLM router skeleton, CLAUDE.md wired |
| **M1 — Studio MVP** | 3w | theme create → RESEARCH/DEEP discovery → Staging save. Basic Need-Fact tickets |
| **M2 — Verification loop** | 2w | material upload → MEDIUM/LOW parse → edge lock → iterative expansion. Validation gate |
| **M3 — Publish pipeline** | 1w | Staging→Production sync, diff/validation report |
| **M4 — Terminal Macro** | 2w | 3D node map, market-cap sizing, depth slider, flow filters, 60fps |
| **M5 — Terminal Micro** | 2w | Company Drawer, product drill-down, trust badges, price chart |
| **M6 — Predict beta** | 3w | news pipeline, momentum score, Ghost Node expand/contract, tooltips |

(Some stages parallelize. ~14 weeks single-track.)

---

## 12. Key metrics (KPIs)

- **Data trust:** share of exposed figures that are `verified`; Need-Fact ticket resolution rate.
- **Engagement:** depth-slider usage, node drill-downs/session, Predict-on rate.
- **Conversion:** Predict (paid) free→paid conversion, retention (D7/D30).
- **Performance:** average canvas fps, Macro→Micro transition latency.

---

## 13. Open issues / decisions needed

1. Market-data vendor selection + licensing cost (real-time vs delayed).
2. Gemini Deep Research (preview) vs Claude + web_search cross-verification ratio/cost.
3. Vector DB: Pinecone (managed) vs pgvector (Postgres-unified) — initial cost/ops.
4. Multilingual (CN/JP) filing-parse quality validation set.
5. Predict disclaimer / regulatory advisory scope.

---

*End of document. Bump version/date on change. The engineering reference is the accompanying `CLAUDE.md`.*
