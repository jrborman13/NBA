# CLAUDE.md — NBA Historical Database

> Operating rules are inherited from the project-root CLAUDE.md at `NBA/`. Not repeated here.

## Context & Goals
Subfolder of the broader NBA project (`/Users/jackborman/Desktop/PycharmProjects/NBA/`).

**What it is:** an ingestion layer that builds a **Supabase** database of historical,
season-by-season NBA stats — primarily the same stats the main NBA Streamlit app already uses —
stored in a well-structured, reusable format.

**Why it exists:** so the data can be pulled cleanly into future Streamlit apps and, potentially,
a standalone website. Storage conventions must serve **both** Streamlit and a future website
built on **FastAPI + Fly.io / Docker**. Design for query-friendly reuse, not one-off scripts.

**Done well =** a reliable, normalized, season-keyed dataset in Supabase that a FastAPI service
or a new Streamlit app can query directly without re-deriving anything.

Reference the parent `NBA/` folder for shared code/memory and connector config.

## Tech Stack
- **Python** + **pandas** for ingestion and cleaning
- **Jupyter notebooks** (`.ipynb`) for exploration and one-off loads
- **SQL / Supabase** (Postgres) as the destination warehouse
- **nba_api** (stats.nba.com) as the primary data source
- **curl_cffi** — curl-impersonate wrapper that mimics Chrome's TLS handshake byte-for-byte,
  used to get past the NBA/WNBA Akamai config that blocks standard request clients

## Data Sources & Connectors
- **Source:** stats.nba.com, via the **existing API calls already in the main app** — reuse/adapt
  the logic in `NBA/combined-app/` and `NBA/streamlit/` rather than reinventing pulls.
- **Destination:** Supabase (NBA project connector). Cleaned/normalized tables are loaded here.
- Credentials/connection for Supabase come from the parent NBA project config — do not hardcode.

## Schema & Storage Conventions
- **Normalized relational tables** keyed by **canonical NBA IDs + season** — e.g. separate
  `players`, `teams`, `player_season_stats`, `team_season_stats`. This keeps the data clean for a
  FastAPI website to query, not just Streamlit.
- **Column naming mirrors the nba_api source style** (SCREAMING_SNAKE_CASE: `TEAM_ID`,
  `PLAYER_ID`, `SEASON`, `OFF_RATING`) to minimize transform friction from the existing app code.
- Season is a first-class column on every stats table; never collapse multiple seasons into one
  row.

## Ingestion Approach
- **Reuse existing calls:** start from the API call patterns in `combined-app/` and `streamlit/`.
- **curl_cffi for Akamai:** when standard `requests`/`nba_api` calls get blocked, route through
  `curl_cffi` with Chrome impersonation.
- **Rate-limit + retry:** throttle and back off on stats.nba.com — don't hammer it or you'll get
  blocked.

## Project Structure
Early-stage; structure fills in as ingestion scripts are added. Suggested layout:
- `raw/` — immutable downloaded data, kept as pulled
- `cleaned/` — transformed outputs (never written back over `raw/`)
- `notebooks/` — `.ipynb` exploration and load notebooks
- `scripts/` — reusable Python ingestion/cleaning modules

## How to Run
- Notebooks: open in Jupyter and run top-to-bottom.
- Scripts: `python scripts/<name>.py` (document specific entry points here as they're created).

## Key Conventions
- **Canonical IDs:** use NBA team and player IDs as join keys across seasons — never join on
  names (franchises relocate/rename; players share names).
- **Raw is immutable:** treat downloaded `raw/` files as read-only. All transformations write to
  separate `cleaned/` outputs.
- **Build for reuse:** every table should be queryable by a future FastAPI service, not just the
  current Streamlit app.

## Gotchas
- **Akamai blocking:** NBA/WNBA endpoints sit behind Akamai. Plain clients get rejected — reach
  for `curl_cffi` Chrome impersonation before assuming an endpoint is dead.
- **Historical schema quirks:** older seasons are missing advanced stats; validate columns exist
  before assuming them.
