# Website Front-End Plan — Multi-Sport Interactive Tools

**Goal:** a real website that houses your interactive tools (NBA now; WNBA / NFL / PGA later),
reading from the Supabase warehouse you've already built. Streamlit stays as the game-time
prototyping surface; this is the public, polished home.

**Recommended stack:** Next.js (React) + Vercel + your existing Supabase, with a small Python
API (FastAPI) only for the handful of tools that must run Python at request time.

> This is a design/reference doc. Nothing here changes the app. Migrate tool-by-tool; no
> big-bang cutover.

---

## 1. Target architecture

```
                          ┌─────────────────────────────┐
   Browser  ───────────▶  │   Next.js app on Vercel      │   (the new front end)
                          │   - React pages / components │
                          │   - server routes for auth   │
                          └──────────┬─────────┬─────────┘
                                     │         │
              reads finished tables  │         │  calls only for live compute
              via Supabase JS client │         │
                                     ▼         ▼
                    ┌────────────────────┐   ┌──────────────────────────┐
                    │  Supabase (yours)  │   │  FastAPI service          │
                    │  Postgres 17       │   │  (Railway / Render)       │
                    │  - materialized     │   │  - prediction_model.py   │
                    │    tables & views   │   │  - PuLP optimizer        │
                    │  - pg_cron refresh  │   │  reads/writes Supabase   │
                    └─────────▲──────────┘   └──────────┬───────────────┘
                              │                          │
                              │  nightly ingest (unchanged)
                              │                          │
                   ┌──────────┴──────────────────────────┴──────────┐
                   │  Existing pipeline: ingest.py, edge functions,  │
                   │  refresh_show_rollups(), nba_api / pbpstats / DK │
                   └──────────────────────────────────────────────────┘
```

The key idea: **the browser reads finished data straight from Supabase.** It only calls the
Python service for the two or three tools whose logic can't be reduced to SQL or a nightly job.

---

## 2. Repo layout

Two workable shapes. Start with **Option A** (simplest), graduate to a monorepo only if the
Python service grows.

**Option A — front end in its own repo, Python stays where it is**
```
sports-web/                     # NEW repo — the website
├── app/                        # Next.js App Router
│   ├── layout.tsx              # global shell, nav, theme
│   ├── page.tsx                # landing: tiles per tool (your Home.py, reimagined)
│   ├── nba/
│   │   ├── hexagon/page.tsx    # first migration target
│   │   ├── team-fit/page.tsx
│   │   └── predictions/page.tsx
│   ├── wnba/ …                 # add sports as folders later
│   └── api/                    # Next server routes (light glue, auth, caching)
├── components/                 # StatCard, Hexagon radar, DataTable, Badge …
├── lib/
│   ├── supabase.ts             # typed Supabase client (anon key, read-only)
│   └── types.ts                # generated from your DB schema
├── package.json
└── .env.local                  # NEXT_PUBLIC_SUPABASE_URL, ANON_KEY, API_BASE_URL

NBA/  (your current repo)       # UNCHANGED — Streamlit + pipeline live on
```

Plus, when you need request-time Python, a tiny service (can live in the `NBA/` repo or its own):
```
NBA/api-service/                # NEW folder — FastAPI
├── main.py                     # /predict, /optimize endpoints
├── requirements.txt            # reuse existing player_app modules
└── Dockerfile
```

**Option B — monorepo** (`apps/web`, `apps/api`, `packages/shared`) — cleaner long-term but more
tooling up front (pnpm/turbo). Not worth it until you have 2+ services. Skip for now.

---

## 3. Your tools, mapped to the three data patterns

| Tool (current page) | Pattern | Why | Migration effort |
|---|---|---|---|
| **Hexagon** (`7_Hexagon.py`) | 🟢 Pure Supabase read | Reads materialized `player_axis_metrics` | **Low** — start here |
| **Team Hexagon** (`8_Team_Hexagon.py`) | 🟢 Pure Supabase read | Reads materialized `team_axis_metrics` | Low |
| **Team Fit** (`9_Team_Fit.py`) | 🟢 Pure Supabase read | Reads `style_fingerprint` / `team_fit` tables | Low |
| **Players** (`2_Players.py`) | 🟢 Mostly read | Game logs + `mv_player_form` / vs-opp matviews | Low–Med |
| **Teams** (`1_Teams.py`) | 🟡 Data fetcher | Pulls NBA API + pbpstats live at runtime | Med — move fetch to cron→Supabase |
| **Passing** (`5_Passing.py`) | 🟡 Data fetcher | `PlayerDashPtPass` from NBA API | Med |
| **Live box scores** (`4_Live.py`) | 🟡 Near-real-time fetch | `nba_api.live` during games | Med — edge function or small API route |
| **Predictions** (`3_Predictions.py`) | 🔴 Python API | ML model + minute-normalization engine | High — FastAPI or nightly batch |
| **DK Optimizer** (`6_DraftKings_Optimizer.py`) | 🔴 Python API | PuLP ILP solver | High — FastAPI on-demand |

**Three patterns explained:**

- 🟢 **Pure Supabase read** — the browser queries a finished table/view directly with the
  Supabase JS client (anon key + row-level security). No Python at request time. This is the
  majority of your hexagon/fit/player work because you already materialized it. *These are your
  first migrations — they prove the stack with almost no backend work.*

- 🟡 **Data fetcher** — data that must be pulled from NBA.com / pbpstats / DK. You already do
  this nightly via `ingest.py` + `refresh_show_rollups()` on pg_cron. For the website, keep that
  pattern: **fetch on a schedule, write to Supabase, browser reads the table.** The only special
  case is live box scores during a game — that wants a short-interval refresh (a Supabase edge
  function every ~30–60s, or a thin Next API route that proxies `nba_api.live`).

- 🔴 **Python API** — logic that genuinely can't become SQL: the ML predictions and the PuLP
  optimizer. Two sub-options:
  - *Nightly batch* — run `generate_predictions_batch.py` on cron, write to the `predictions`
    table, browser reads it. Zero request-time Python. Best for the slate-wide predictions.
  - *On-demand FastAPI* — for the optimizer (user picks salary/constraints, needs a live solve),
    stand up a `/optimize` endpoint. Reuses your existing `player_app` modules unchanged.
  - **Parity note:** your CLAUDE.md prediction-parity rule still applies — any factor added to
    the FastAPI `/predict` path must also live in `generate_predictions_batch.py` and the
    Predictions page. The API becomes a *third* consumer of the same shared `player_app` logic,
    which is fine as long as the factor lives in the shared module, not the endpoint.

---

## 4. First-tool migration plan — **Hexagon**

Best starter: it's a single materialized read + one visual (radar chart), so you learn Next.js
+ Supabase + charting without touching any Python.

1. **Scaffold** — `npx create-next-app@latest sports-web` (TypeScript, App Router, Tailwind).
   Deploy the empty app to Vercel from a GitHub push on day one so the pipeline works before
   there's anything to break.
2. **Connect Supabase** — `npm i @supabase/supabase-js`; put URL + anon key in `.env.local` and
   Vercel env vars. Generate TypeScript types from your schema
   (`supabase gen types typescript`) so queries are typed.
3. **RLS check** — the browser uses the anon key, so enable row-level security on
   `player_axis_metrics` (or expose a read-only view) with a `SELECT` policy for `anon`. This is
   the one security step people skip — do it before going public.
4. **Data function** — a `lib/getHexagon.ts` that queries season/player and returns the six axis
   values. Mirror the query your `7_Hexagon.py` already runs.
5. **Chart** — render the radar with a React charting lib (Recharts is simplest; Plotly-react if
   you want to match your current Plotly look; Nivo/visx for more control).
6. **Component** — build a reusable `<Hexagon player=… season=… />` plus the `StatCard`/`Badge`
   patterns from the `ui_theme.py` work, now as real React components.
7. **Ship it** at `sports-web.vercel.app/nba/hexagon`, get a domain, done. Then repeat for Team
   Hexagon and Team Fit (same shape), *then* tackle a 🟡 fetcher, *then* a 🔴 Python tool.

**Budget the first tool as slow** — you're learning React/TypeScript/JSX. Tools 2–3 go 3–4× faster.

---

## 5. Costs (verified July 2026)

All three platforms have real free tiers, so **Phase 0 is ~$0 incremental** (your Supabase is
already provisioned and paid for — the website just adds read traffic to it).

| Service | Free tier | Paid entry | Notes |
|---|---|---|---|
| **Vercel** (front end) | Hobby **$0** — 100 GB transfer, 1 M function calls. *Non-commercial only.* | Pro **$20**/user/mo (incl. $20 usage credit) | Move to Pro when the site is public/monetized or exceeds hobby limits |
| **Supabase** (warehouse) | Free **$0** — 2 projects, 500 MB DB (pauses on inactivity) | Pro **$25**/mo — 8 GB DB, $10 compute credit, no pausing | ⚠️ Your warehouse (3 GB+ `play_by_play`, etc.) is **already past the free tier**, so you're effectively already on Pro. Website adds ~$0 marginal. |
| **Python API** (only if needed) | Render free tier (spins down); Fly.io trial | Railway **$5**/mo (incl. $5 credit) · Render Starter **$7**/mo | Skip entirely if you go nightly-batch instead of on-demand |
| **Domain** | — | ~**$12–15**/yr | e.g. Namecheap/Cloudflare |

**Realistic monthly totals (incremental over what you pay Supabase today):**

- **Phase 0 — learning / 1–3 read-only tools, non-commercial:**
  Vercel Hobby $0 + Supabase (already paid) + no Python service = **~$0/mo** (+ domain ~$1/mo).
- **Phase 1 — public site, a few tools, some request-time Python:**
  Vercel Pro $20 + Railway/Render $5–7 = **~$25–30/mo** incremental.
- **Phase 2 — multi-sport, real traffic, live compute:**
  Vercel Pro $20 (+ possible usage overage) + Supabase overages $0–50 + Python API $10–25 =
  **~$55–120/mo**, scaling with traffic.

Two cost traps to know: **Vercel Hobby is non-commercial** — if you ever put ads or monetize,
you need Pro. And **Supabase/Vercel usage overages** are the thing that surprises people — both
bill pay-as-you-go above the included limits, so watch data transfer and function invocations as
traffic grows (caching finished tables aggressively keeps this near zero).

---

## 6. Honest caveats

- **React/TypeScript is a real ramp from Python.** The first tool will feel slow. This is the
  main cost of the project, and it's a learning cost, not a dollar cost.
- **You don't have to migrate everything.** The 🔴 Python tools (Predictions, Optimizer) are the
  hardest — leave them on Streamlit longest, or expose them as nightly-batch reads first and only
  build the FastAPI endpoint when you actually need on-demand solves.
- **Keep Streamlit.** It stays your fastest path for game-time experiments and one-off analysis.
  The website is for the tools that are polished enough to show off.
- **Security:** the anon key + RLS model is safe *only if RLS is on*. Never ship the service-role
  key to the browser. All writes stay server-side (cron, edge functions, FastAPI).

---

*Verified pricing sources listed alongside this plan in chat.*
