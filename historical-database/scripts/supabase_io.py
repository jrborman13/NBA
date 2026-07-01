"""
Supabase I/O: JSONB-payload upserts, the ingestion_log, and DataFrame->row helpers.

Connection comes from env (do NOT hardcode — see parent NBA project config / .env.example):
    SUPABASE_URL, SUPABASE_SERVICE_KEY   (service key = write access)

Every stat table follows the same shape: typed identity/key columns + a JSONB `stats`
column holding the full nba_api row. `rows_from_df` builds that shape generically so each
endpoint only declares its identity columns.
"""

import os
import math
import json
import time
import httpx
import pandas as pd
from supabase import create_client, Client
from postgrest.exceptions import APIError

_client: Client | None = None
_BATCH = 500  # Supabase/PostgREST handles a few hundred rows per request comfortably

# Destination Postgres schema. None -> public (NBA legacy, pre-schema-move). Set to 'wnba'
# (or 'nba' after the NBA move) so the same pipeline writes each league into its own schema.
SCHEMA: str | None = None


def _tbl(name: str):
    c = client()
    return c.schema(SCHEMA).table(name) if SCHEMA else c.table(name)


def _rpc(fn: str):
    # .schema(x).rpc() is the postgrest client whose rpc(func, params) requires params; pass {}.
    c = client().schema(SCHEMA) if SCHEMA else client()
    return c.rpc(fn, {})

# Transport-level failures (connection drops, HTTP/2 ConnectionTerminated, timeouts, protocol
# errors) — transient, retry with a fresh client. NOT data errors (those are postgrest.APIError).
_RETRYABLE = (httpx.TransportError,)


def client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_ANON_KEY"]
        _client = create_client(url, key)
    return _client


def _transient(exc) -> bool:
    """True for retryable Supabase failures: transport drops (httpx) and PostgREST schema-cache
    reloads (PGRST002/PGRST001 — emitted while PostgREST re-introspects after a schema change;
    the message literally says 'Retrying'). NOT real data/constraint errors."""
    if isinstance(exc, _RETRYABLE):
        return True
    if isinstance(exc, APIError):
        return getattr(exc, "code", None) in ("PGRST002", "PGRST001") or \
               "schema cache" in (getattr(exc, "message", "") or "")
    return False


def _db(fn, *, retries=8, base=0.5):
    """Run a Supabase op, retrying on transient failures (connection drops + PostgREST schema-cache
    reloads). Long runs outlive a single HTTP/2 connection; a fresh client is dialed on each retry.
    `fn` must call client() itself. Non-transient errors (constraint violations etc.) re-raise."""
    global _client
    last = None
    for attempt in range(retries):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — classify, retry transient, re-raise the rest
            if not _transient(exc):
                raise
            last = exc
            _client = None  # force a fresh connection on the next attempt
            delay = base * (2 ** attempt)
            print(f"  [db-retry {attempt + 1}/{retries}] {type(exc).__name__}: {str(exc)[:60]} -> {delay:.1f}s")
            time.sleep(delay)
    raise last


def _json_safe(value):
    """Recursively coerce a value into something the Supabase/httpx JSON encoder accepts.

    The encoder rejects non-finite floats (NaN/Inf) — and nba_api frames are full of NaN
    (undrafted players, missing advanced stats). numpy scalars, NaT, dates and Timestamps
    also need normalizing. Lists/dicts are walked (ScheduleLeagueV2 has nested fields)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, int):
        return value
    if hasattr(value, "item"):                 # numpy scalar -> python scalar
        v = value.item()
        return _json_safe(v)
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    try:                                        # pandas NA / NaT
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        return value
    return str(value)                           # dates, Timestamps, Decimals, etc.


def _clean(value):
    """JSON/PostgREST-safe scalar for a typed key column (NaN/NaT -> None, numpy -> python).

    Also coerces integral floats to int: pandas widens int columns to float64 when the frame
    has NaN, so a value like DRAFT_NUMBER arrives as 15.0 and Postgres rejects "15.0" for an
    INT column. Non-integral floats (e.g. MIN 28.4 -> NUMERIC) are left as floats."""
    v = _json_safe(value)
    if isinstance(v, str) and v.strip() == "":
        return None          # "" -> NULL (PlayByPlayV3 sends "" for scoreHome/Away pre-score, etc.)
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def rows_from_df(df: pd.DataFrame, identity: dict, id_map: dict[str, str],
                 constants: dict | None = None, include_stats: bool = True) -> list[dict]:
    """
    Turn an nba_api DataFrame into upsert rows: identity/key columns + JSONB `stats`.

    identity   : columns whose value is the SAME for every row (e.g. season, season_type, measure_type)
    id_map     : {db_column: SOURCE_DF_COLUMN} promoted to typed columns (e.g. {"team_id": "TEAM_ID"})
    constants  : extra static columns (e.g. {"per_mode": "PerGame"})
    include_stats : store the full raw row under JSONB `stats`. Set False for play_by_play —
                    the per-event JSONB is huge (~700 bytes/row) and the typed columns capture
                    everything useful, so we drop it to keep that table ~10x smaller.
    """
    if df is None or df.empty:
        return []
    constants = constants or {}
    rows = []
    for rec in df.to_dict(orient="records"):
        row = dict(identity)
        row.update(constants)
        for db_col, src_col in id_map.items():
            row[db_col] = _clean(rec.get(src_col))
        if include_stats:
            row["stats"] = {k: _json_safe(v) for k, v in rec.items()}  # NaN/Inf/Timestamp-safe
        rows.append(row)
    return rows


def upsert(table: str, rows: list[dict], pk: list[str]):
    """Idempotent upsert in batches, keyed by pk columns."""
    if not rows:
        return 0
    # Drop rows with a NULL pk column — PK columns are NOT NULL, so these always fail (e.g. WNBA
    # LeagueDashPlayerStats emits aggregate rows with null player_id/name). Skip them silently.
    rows = [r for r in rows if all(r.get(c) is not None for c in pk)]
    if not rows:
        return 0
    # Dedup within the batch by pk — PostgREST errors ("ON CONFLICT ... cannot affect row a
    # second time") if two rows in one command share the pk. Some endpoints emit dup keys
    # (e.g. GameRotation: a player with the same in_time_real twice). Keep the last.
    _seen = {}
    for r in rows:
        _seen[tuple(r.get(c) for c in pk)] = r
    rows = list(_seen.values())
    on_conflict = ",".join(pk)
    total = 0
    for i in range(0, len(rows), _BATCH):
        chunk = rows[i:i + _BATCH]
        _db(lambda c=chunk: _tbl(table).upsert(c, on_conflict=on_conflict).execute())
        total += len(chunk)
    return total


# --- ingestion_log: resume/skip support ------------------------------------
def already_done(endpoint: str, season: str = None, season_type: str = None,
                 scope: str = "all") -> bool:
    """True if this unit of work is already logged ok (so the run can skip it)."""
    def _run():
        q = (_tbl("ingestion_log").select("status")
             .eq("endpoint", endpoint).eq("scope", scope).eq("status", "ok"))
        if season is not None:
            q = q.eq("season", season)
        if season_type is not None:
            q = q.eq("season_type", season_type)
        return q.execute()
    return bool(_db(_run).data)


def log(endpoint: str, season: str = None, season_type: str = None, scope: str = "all",
        df: pd.DataFrame = None, status: str = None, error_msg: str = None):
    """Record the outcome of a scrape unit. Infers status from df if not given.

    season/season_type are part of the ingestion_log PRIMARY KEY (NOT NULL), but per-game
    units like PlayByPlay log with no season — coerce None -> '' so the upsert doesn't blow
    up on a NULL-PK violation."""
    if status is None:
        status = "empty" if (df is None or df.empty) else "ok"
    row = {"endpoint": endpoint, "season": season or "", "season_type": season_type or "",
           "scope": scope, "row_count": 0 if df is None else int(len(df)),
           "status": status, "error_msg": error_msg}
    _db(lambda: _tbl("ingestion_log").upsert(
        row, on_conflict="endpoint,season,season_type,scope").execute())


# game_type code (GAME_ID[2]) -> season_type label. Used to stamp pbp events + schedule rows.
GAME_TYPE_TO_SEASON_TYPE = {"1": "Preseason", "2": "Regular Season", "3": "All-Star",
                            "4": "Playoffs", "5": "Play-In", "6": "Play-In"}


def _select_all(table: str, columns: str, filters, order: str) -> list[dict]:
    """Fetch ALL rows from a filtered select, paging past PostgREST's 1000-row cap via .range().
    `order` MUST be a stable (ideally unique) column — without an explicit ORDER BY, PostgREST's
    row order is not guaranteed consistent across .range() pages, so pages overlap/skip and the
    result silently under/over-counts. `filters` is applied to each page. Retries on transients."""
    out, page, step = [], 0, 1000
    while True:
        def _run(p=page):
            q = _tbl(table).select(columns)
            q = filters(q)
            return q.order(order).range(p * step, p * step + step - 1).execute()
        batch = _db(_run).data or []
        out.extend(batch)
        if len(batch) < step:
            return out
        page += 1


def get_game_ids(seasons: list[str], game_types=("2", "4", "6")) -> list[tuple]:
    """Enumerate (game_id, season, season_type) from `schedule` for the play-by-play pass,
    so each event can be stamped with its season + season_type (derived from game_type).
    Pages past the 1000-row cap — there are ~25k games across all seasons."""
    rows = _select_all("schedule", "game_id, game_type, season",
                       lambda q: q.in_("season", seasons), order="game_id")
    out = []
    for r in rows:
        gt = r.get("game_type")
        if gt in game_types:
            out.append((r["game_id"], r.get("season"),
                        GAME_TYPE_TO_SEASON_TYPE.get(gt, "Regular Season")))
    return out


def seed_players_from_stats() -> int:
    """Insert any player_id present in player_season_stats but missing from `players`.

    PlayerIndex is thin for past seasons (~140 rows), so the dimension would be incomplete if
    built from it alone. This calls a set-based, insert-only DB function (ON CONFLICT DO NOTHING)
    so PlayerIndex bio is preserved for players already present. Returns rows inserted."""
    data = _db(lambda: _rpc("seed_players_from_stats").execute()).data
    if isinstance(data, int):
        return data
    if isinstance(data, list) and data:
        return data[0] if isinstance(data[0], int) else 0
    return 0


def get_done_scopes(endpoint: str) -> set:
    """All scopes already logged 'ok' for an endpoint, in ONE paged query. Lets per-game tiers
    (pbp, rotation) skip completed work in-memory instead of an already_done() round-trip per
    game — turns a ~20k-call resume skip-scan into a single fetch."""
    rows = _select_all("ingestion_log", "scope",
                       lambda q: q.eq("endpoint", endpoint).eq("status", "ok"), order="scope")
    return {r["scope"] for r in rows}


def get_team_ids() -> list[int]:
    """Team ids from the `teams` dimension (league-aware via SCHEMA). Drives the per-team
    on/off loop for leagues without a static team list (WNBA)."""
    rows = _select_all("teams", "team_id", lambda q: q, order="team_id")
    return sorted({r["team_id"] for r in rows})


def get_rostered_player_ids(season: str, season_type: str = "Regular Season") -> list[int]:
    """Player ids that actually appear in a season (drive PlayerDashPtPass / per-player calls).
    Pages past the 1000-row cap — a season has ~1700 player_season_stats rows (3 measure types),
    so a single .execute() would silently drop ~1/3 of the players from the passing pull."""
    rows = _select_all("player_season_stats", "player_id",
                       lambda q: q.eq("season", season).eq("season_type", season_type), order="player_id")
    return sorted({r["player_id"] for r in rows})
