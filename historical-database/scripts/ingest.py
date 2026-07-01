"""
NBA historical backfill orchestrator (skeleton).

Runs the tiers in dependency order (see RUNBOOK.md):
  dimensions -> tier 1 -> tier 2 -> tier 3 -> play-by-play

Every write is an idempotent upsert keyed by table PK; progress is logged to
`ingestion_log` so an interrupted run resumes instead of restarting.

Fill in the TODOs per endpoint using ENDPOINTS_TO_SCRAPE.md for params and
schema.sql for the target columns. Keep raw nba_api rows in the JSONB `stats` column.
"""

import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from dotenv import load_dotenv
load_dotenv()

import nba_api.stats.endpoints as ep
from nba_api.stats.static import teams as static_teams

# Local helpers
import supabase_io
from league import get_league, season_string
from nba_session import patch_nba_session, safe_call, stats_json_via_zenrows
from supabase_io import (upsert, already_done, log, rows_from_df,
                         get_game_ids, get_rostered_player_ids, get_done_scopes, get_team_ids,
                         seed_players_from_stats, GAME_TYPE_TO_SEASON_TYPE)

# League config (LEAGUE=nba|wnba env; default nba). Drives host, league_id, season format,
# destination schema, and which tiers exist.
CFG = get_league()
LID = CFG["league_id"]
supabase_io.SCHEMA = CFG["schema"]      # None=public (NBA legacy), 'wnba', or 'nba' post-move

SEASON_TYPES = ["Regular Season", "Playoffs"]
TEAM_MEASURES = ["Base", "Advanced", "Misc", "Four Factors"]
PLAYER_MEASURES = ["Base", "Advanced", "Misc"]
PLAY_TYPES = ["Isolation", "Transition", "PRBallHandler", "PRRollman", "Postup",
              "Spotup", "Handoff", "Cut", "OffScreen", "OffRebound", "Misc"]
PT_MEASURES = ["Drives", "Passing", "Possessions", "CatchShoot", "PullUpShot", "Rebounding"]
# Part A tracking dashboards (defense / hustle / shot-splits). Category strings confirmed via
# endpoint_cutoffs.py --new-only probe (all return data 2013-14+; hustle 2015-16+).
DEFENSE_CATEGORIES = ["Overall", "3 Pointers", "2 Pointers", "Less Than 6Ft",
                      "Less Than 10Ft", "Greater Than 15Ft"]
DRIBBLE_RANGES = ["0 Dribbles", "1 Dribble", "2 Dribbles", "3-6 Dribbles", "7+ Dribbles"]
CLOSE_DEF_RANGES = ["0-2 Feet - Very Tight", "2-4 Feet - Tight", "4-6 Feet - Open",
                    "6+ Feet - Wide Open"]
THROTTLE = 0.8  # seconds between calls (eased from 0.6 to reduce sustained-throttle on long runs)
# GameRotation via ZenRows is high-latency per call (~15s; ZenRows retries NBA internally) but the
# Business plan allows 100 concurrent requests, so fan out. Upserts stay serial in the main thread.
ROT_WORKERS = int(os.getenv("ROT_WORKERS", "50"))
# Adaptive circuit-breaker for the ZenRows rotation pull: process in batches and, when the rolling
# post-retry success rate drops, pause-and-cool (escalating) so a sustained run doesn't dig NBA's
# Akamai throttle deeper — the discipline missing from the first attempt. All tunable via env.
ROT_BATCH = int(os.getenv("ROT_BATCH", "30"))           # games per batch / breaker check point
ROT_BREAKER = float(os.getenv("ROT_BREAKER", "0.70"))   # cool down if rolling success < this
ROT_WINDOW = int(os.getenv("ROT_WINDOW", "60"))         # rolling-window size for the success rate

# Endpoint availability cut-offs (measured 2005-06→2024-25 via scripts/endpoint_cutoffs.py).
# Pre-cutoff seasons return empty for these, so skip them on a cyclical run instead of
# firing hundreds of guaranteed-empty calls. Everything else goes back to 2005-06.
TRACKING_FIRST_YEAR = 2013   # LeagueDashPtStats + PlayerDashPtPass start 2013-14
SYNERGY_FIRST_YEAR = 2012    # SynergyPlayTypes starts 2012-13
HUSTLE_FIRST_YEAR = 2015     # LeagueHustleStats start 2015-16 (per endpoint_cutoffs probe)


def _start_year(season: str) -> int:
    return int(season[:4])


def _iso_dates(series):
    """Normalize a date column to ISO 'YYYY-MM-DD' strings (NaT -> NaN -> None downstream).
    nba_api dates arrive in mixed shapes — schedule '10/04/2024 00:00:00' (US MDY+time),
    game logs '2025-04-13T00:00:00' (ISO+time). pandas parses both; we store clean dates."""
    return pd.to_datetime(series, errors="coerce").dt.strftime("%Y-%m-%d")


# Per-run caps (0 = no cap). Set from CLI in main(). Used to smoke-test a season cheaply and
# to chunk the long per-entity / per-game passes into resumable batches.
MAX_ENTITIES = 0   # caps per-team on/off + per-player passing loops in tier 2
MAX_GAMES = 0      # caps games scraped in the play-by-play pass


def seasons_between(start: str, end: str) -> list[str]:
    s, e = int(start[:4]), int(end[:4])
    return [season_string(CFG, y) for y in range(s, e + 1)]


# --- Dimensions -------------------------------------------------------------
def load_dimensions(seasons):
    if CFG["teams_static"]:
        rows = [
            {"team_id": t["id"], "abbreviation": t["abbreviation"], "nickname": t["nickname"],
             "city": t["city"], "full_name": t["full_name"], "state": t["state"],
             "year_founded": t["year_founded"]}
            for t in static_teams.get_teams()
        ]
    else:
        # No static WNBA team list — build from the latest season's team stats.
        tdf = safe_call(ep.LeagueDashTeamStats, season=seasons[-1], season_type_all_star="Regular Season",
                        measure_type_detailed_defense="Base", per_mode_detailed="PerGame", league_id_nullable=LID)
        rows = [{"team_id": int(r["TEAM_ID"]), "abbreviation": r.get("TEAM_ABBREVIATION"),
                 "full_name": r.get("TEAM_NAME")} for r in tdf.to_dict("records")] if tdf is not None else []
    upsert("teams", rows, pk=["team_id"])

    for season in seasons:
        df = safe_call(ep.PlayerIndex, season=season, league_id=LID)
        rows = rows_from_df(
            df, identity={}, constants={"last_season_seen": season},
            id_map={"player_id": "PERSON_ID", "first_name": "PLAYER_FIRST_NAME",
                    "last_name": "PLAYER_LAST_NAME", "player_slug": "PLAYER_SLUG",
                    "position": "POSITION", "height": "HEIGHT", "weight": "WEIGHT",
                    "college": "COLLEGE", "country": "COUNTRY", "draft_year": "DRAFT_YEAR",
                    "draft_round": "DRAFT_ROUND", "draft_number": "DRAFT_NUMBER",
                    "from_year": "FROM_YEAR", "to_year": "TO_YEAR"})
        upsert("players", rows, pk=["player_id"])
        time.sleep(THROTTLE)


# --- Seed players dimension from season stats (run after Tier 1) -------------
def seed_players(seasons):
    """Complete the `players` dimension from player_season_stats. PlayerIndex (in dims) is thin
    for past seasons, so this back-fills every player who has stats — insert-only, so PlayerIndex
    bio is preserved. Depends on Tier 1 having populated player_season_stats."""
    n = seed_players_from_stats()
    print(f"  seeded {n} players from player_season_stats (insert-only; PlayerIndex bio kept)")


# --- Tier 1 -----------------------------------------------------------------
def tier1(seasons):
    for season in seasons:
        for st in SEASON_TYPES:
            for m in TEAM_MEASURES:
                if already_done("LeagueDashTeamStats", season, st, m):
                    continue
                df = safe_call(ep.LeagueDashTeamStats, season=season, season_type_all_star=st,
                               measure_type_detailed_defense=m, per_mode_detailed="PerGame",
                               league_id_nullable=LID)
                rows = rows_from_df(
                    df, identity={"season": season, "season_type": st, "measure_type": m},
                    constants={"per_mode": "PerGame"},
                    id_map={"team_id": "TEAM_ID", "team_name": "TEAM_NAME",
                            "gp": "GP", "min": "MIN"})
                upsert("team_season_stats", rows,
                       pk=["season", "season_type", "team_id", "measure_type", "per_mode"])
                log("LeagueDashTeamStats", season, st, scope=m, df=df)
                time.sleep(THROTTLE)

            for m in PLAYER_MEASURES:
                if already_done("LeagueDashPlayerStats", season, st, m):
                    continue
                df = safe_call(ep.LeagueDashPlayerStats, season=season, season_type_all_star=st,
                               measure_type_detailed_defense=m, per_mode_detailed="PerGame",
                               league_id_nullable=LID)
                rows = rows_from_df(
                    df, identity={"season": season, "season_type": st, "measure_type": m},
                    constants={"per_mode": "PerGame"},
                    id_map={"player_id": "PLAYER_ID", "player_name": "PLAYER_NAME",
                            "team_id": "TEAM_ID", "gp": "GP", "min": "MIN"})
                upsert("player_season_stats", rows,
                       pk=["season", "season_type", "player_id", "measure_type", "per_mode"])
                log("LeagueDashPlayerStats", season, st, scope=m, df=df)
                time.sleep(THROTTLE)

        # standings: regular season only. WNBA needs V3 (V1 returns empty); same columns.
        if not already_done("LeagueStandings", season, "Regular Season", "all"):
            _stand = ep.LeagueStandingsV3 if CFG["standings_v3"] else ep.LeagueStandings
            df = safe_call(_stand, league_id=LID, season=season, season_type="Regular Season")
            rows = rows_from_df(
                df, identity={"season": season},
                id_map={"team_id": "TeamID", "conference": "Conference", "division": "Division",
                        "wins": "WINS", "losses": "LOSSES", "win_pct": "WinPCT",
                        "playoff_rank": "PlayoffRank"})
            upsert("team_standings", rows, pk=["season", "team_id"])
            log("LeagueStandings", season, "Regular Season", scope="all", df=df)
            time.sleep(THROTTLE)


# --- Tier 2 -----------------------------------------------------------------
def tier2(seasons):
    for season in seasons:
        for st in SEASON_TYPES:
            # --- Clutch ---  (already_done -> resumable after a crash mid-backfill)
            if not already_done("LeagueDashTeamClutch", season, st, scope="Advanced"):
                tc = safe_call(ep.LeagueDashTeamClutch, season=season, season_type_all_star=st,
                               per_mode_detailed="PerGame", measure_type_detailed_defense="Advanced",
                               league_id_nullable=LID)
                upsert("team_season_clutch",
                       rows_from_df(tc, identity={"season": season, "season_type": st},
                                    constants={"per_mode": "PerGame"}, id_map={"team_id": "TEAM_ID"}),
                       pk=["season", "season_type", "team_id", "per_mode"])
                log("LeagueDashTeamClutch", season, st, scope="Advanced", df=tc)
                time.sleep(THROTTLE)

            if not already_done("LeagueDashPlayerClutch", season, st, scope="Advanced"):
                pc = safe_call(ep.LeagueDashPlayerClutch, season=season, season_type_all_star=st,
                               per_mode_detailed="PerGame", measure_type_detailed_defense="Advanced",
                               league_id_nullable=LID)
                upsert("player_season_clutch",
                       rows_from_df(pc, identity={"season": season, "season_type": st},
                                    constants={"per_mode": "PerGame"},
                                    id_map={"player_id": "PLAYER_ID", "team_id": "TEAM_ID"}),
                       pk=["season", "season_type", "player_id", "per_mode"])
                log("LeagueDashPlayerClutch", season, st, scope="Advanced", df=pc)
                time.sleep(THROTTLE)

            # --- Player tracking (LeagueDashPtStats) --- NBA 2013-14+; WNBA has none
            _track = CFG["has_tracking"] and _start_year(season) >= TRACKING_FIRST_YEAR
            for pt in (PT_MEASURES if _track else []):
                for who in ("Player", "Team"):
                    if already_done("LeagueDashPtStats", season, st, scope=f"{pt}:{who}"):
                        continue
                    df = safe_call(ep.LeagueDashPtStats, season=season, season_type_all_star=st,
                                   pt_measure_type=pt, player_or_team=who, per_mode_simple="PerGame",
                                   league_id_nullable=LID)
                    if who == "Player":
                        rows = rows_from_df(
                            df, identity={"season": season, "season_type": st, "pt_measure_type": pt},
                            constants={"per_mode": "PerGame"},
                            id_map={"player_id": "PLAYER_ID", "team_id": "TEAM_ID"})
                        upsert("pt_tracking_player", rows,
                               pk=["season", "season_type", "player_id", "pt_measure_type", "per_mode"])
                    else:
                        rows = rows_from_df(
                            df, identity={"season": season, "season_type": st, "pt_measure_type": pt},
                            constants={"per_mode": "PerGame"}, id_map={"team_id": "TEAM_ID"})
                        upsert("pt_tracking_team", rows,
                               pk=["season", "season_type", "team_id", "pt_measure_type", "per_mode"])
                    log("LeagueDashPtStats", season, st, scope=f"{pt}:{who}", df=df)
                    time.sleep(THROTTLE)

            # --- Synergy play types --- NBA 2012-13+; WNBA has none
            _syn = CFG["has_tracking"] and _start_year(season) >= SYNERGY_FIRST_YEAR
            for pty in (PLAY_TYPES if _syn else []):
                for grp in ("offensive", "defensive"):
                    for abbr in ("P", "T"):
                        if already_done("SynergyPlayTypes", season, st, scope=f"{pty}:{grp}:{abbr}"):
                            continue
                        try:
                            df = safe_call(ep.SynergyPlayTypes, league_id=LID, season=season,
                                           season_type_all_star=st, per_mode_simple="Totals",
                                           player_or_team_abbreviation=abbr,
                                           type_grouping_nullable=grp, play_type_nullable=pty)
                        except Exception as exc:  # one throttled unit must not abort the backfill
                            log("SynergyPlayTypes", season, st, scope=f"{pty}:{grp}:{abbr}",
                                status="error", error_msg=str(exc)[:300])
                            print(f"  [SKIP] synergy {season}/{st} {pty}:{grp}:{abbr}: {exc}")
                            time.sleep(THROTTLE)
                            continue
                        ent_col = "PLAYER_ID" if abbr == "P" else "TEAM_ID"
                        rows = rows_from_df(
                            df, identity={"season": season, "season_type": st, "entity_type": abbr,
                                          "play_type": pty, "type_grouping": grp},
                            constants={"per_mode": "Totals"},
                            id_map={"entity_id": ent_col, "team_id": "TEAM_ID"})
                        upsert("synergy_playtypes", rows,
                               pk=["season", "season_type", "entity_type", "entity_id",
                                   "team_id", "play_type", "type_grouping"])
                        log("SynergyPlayTypes", season, st, scope=f"{pty}:{grp}:{abbr}", df=df)
                        time.sleep(THROTTLE)

            # --- Team on/off (per team) ---
            if CFG["teams_static"]:
                from nba_api.stats.static import teams as _t
                onoff_team_ids = [t["id"] for t in _t.get_teams()]
            else:
                onoff_team_ids = get_team_ids()  # WNBA: from the teams dimension
            if MAX_ENTITIES:
                onoff_team_ids = onoff_team_ids[:MAX_ENTITIES]
            for _tid in onoff_team_ids:
                if already_done("TeamPlayerOnOffDetails", season, st, scope=str(_tid)):
                    continue
                try:
                    frames = safe_call(ep.TeamPlayerOnOffDetails, team_id=_tid, season=season,
                                       season_type_all_star=st, per_mode_detailed="Totals",
                                       measure_type_detailed_defense="Advanced", _all_frames=True,
                                       league_id_nullable=LID)
                except Exception as exc:  # one throttled unit must not abort the backfill
                    log("TeamPlayerOnOffDetails", season, st, scope=str(_tid),
                        status="error", error_msg=str(exc)[:300])
                    print(f"  [SKIP] on/off {season}/{st} team {_tid}: {exc}")
                    time.sleep(THROTTLE)
                    continue
                for idx, onoff in ((1, "ON"), (2, "OFF")):  # NBA TeamPlayerOnOffDetails: frame 1 = OnCourt, 2 = OffCourt
                    if len(frames) > idx:
                        rows = rows_from_df(
                            frames[idx],
                            identity={"season": season, "season_type": st, "team_id": _tid,
                                      "on_off": onoff},
                            constants={"measure_type": "Advanced", "per_mode": "Totals"},
                            id_map={"player_id": "VS_PLAYER_ID"})
                        upsert("team_player_onoff", rows,
                               pk=["season", "season_type", "team_id", "player_id", "on_off"])
                log("TeamPlayerOnOffDetails", season, st, scope=str(_tid), df=frames[0])
                time.sleep(THROTTLE)

            # --- Passing (per rostered player) --- NBA 2013-14+; WNBA has none
            passing_pids = (get_rostered_player_ids(season, st)
                            if (CFG["has_tracking"] and _start_year(season) >= TRACKING_FIRST_YEAR) else [])
            if MAX_ENTITIES:
                passing_pids = passing_pids[:MAX_ENTITIES]
            for pid in passing_pids:
                if already_done("PlayerDashPtPass", season, st, scope=str(pid)):
                    continue
                try:
                    frames = safe_call(ep.PlayerDashPtPass, player_id=pid, team_id=0, season=season,
                                       season_type_all_star=st, per_mode_simple="PerGame",
                                       _all_frames=True)
                except Exception as exc:  # one throttled unit must not abort the backfill
                    log("PlayerDashPtPass", season, st, scope=str(pid),
                        status="error", error_msg=str(exc)[:300])
                    print(f"  [SKIP] passing {season}/{st} pid {pid}: {exc}")
                    time.sleep(THROTTLE)
                    continue
                for fr, direction in zip(frames, ("made", "received")):
                    rows = rows_from_df(
                        fr, identity={"season": season, "season_type": st, "player_id": pid,
                                      "pass_direction": direction},
                        id_map={"team_id": "TEAM_ID", "pass_teammate_player_id": "PASS_TEAMMATE_PLAYER_ID"})
                    upsert("player_passing", rows,
                           pk=["season", "season_type", "player_id", "team_id",
                               "pass_teammate_player_id", "pass_direction"])
                log("PlayerDashPtPass", season, st, scope=str(pid),
                    df=frames[0] if frames else None)
                time.sleep(THROTTLE)


# --- Tier 3 -----------------------------------------------------------------
def tier3(seasons):
    for season in seasons:
        # Schedule is per-season (covers all game types); load once, derive game_type.
        # already_done -> resumable; try/except -> one throttle doesn't abort the tier.
        if not already_done("ScheduleLeagueV2", season, "all", scope="all"):
            try:
                sched = safe_call(ep.ScheduleLeagueV2, season=season, league_id=LID)
                if sched is not None and not sched.empty:
                    sched = sched.copy()
                    gid = "GAME_ID" if "GAME_ID" in sched.columns else "gameId"
                    sched["__gtype"] = sched[gid].astype(str).str[2]
                    # season_type is per-row (schedule mixes preseason/RS/playoffs/play-in);
                    # derive it from game_type rather than hardcoding "Regular Season".
                    sched["__stype"] = sched["__gtype"].map(GAME_TYPE_TO_SEASON_TYPE).fillna("Regular Season")
                    sched["gameDate"] = _iso_dates(sched["gameDate"])
                    # ScheduleLeagueV2 returns camelCase, flattened/nested columns (gameDate,
                    # homeTeam_teamId, awayTeam_teamId) — NOT SCREAMING_SNAKE_CASE.
                    rows = rows_from_df(
                        sched, identity={"season": season},
                        id_map={"game_id": gid, "season_type": "__stype", "game_date": "gameDate",
                                "home_team_id": "homeTeam_teamId", "away_team_id": "awayTeam_teamId",
                                "game_type": "__gtype"})
                    upsert("schedule", rows, pk=["game_id"])
                log("ScheduleLeagueV2", season, "all", scope="all", df=sched)
            except Exception as exc:
                log("ScheduleLeagueV2", season, "all", scope="all", status="error", error_msg=str(exc)[:300])
                print(f"  [SKIP] schedule {season}: {exc}")
            time.sleep(THROTTLE)

        for st in SEASON_TYPES:
            # stats.nba.com now rejects empty MeasureType / 'None' OpponentTeamID on the
            # *GameLogs endpoints ({"MeasureType":["Invalid parameters"]}). Pass both explicitly.
            if not already_done("TeamGameLogs", season, st, scope="all"):
                try:
                    tlogs = safe_call(ep.TeamGameLogs, season_nullable=season, season_type_nullable=st,
                                      measure_type_player_game_logs_nullable="Base", opp_team_id_nullable=0,
                                      league_id_nullable=LID)
                    if tlogs is not None and not tlogs.empty:
                        tlogs = tlogs.copy()
                        tlogs["GAME_DATE"] = _iso_dates(tlogs["GAME_DATE"])
                    upsert("team_game_logs",
                           rows_from_df(tlogs, identity={"season": season, "season_type": st},
                                        id_map={"team_id": "TEAM_ID", "game_id": "GAME_ID",
                                                "game_date": "GAME_DATE", "matchup": "MATCHUP",
                                                "wl": "WL", "min": "MIN"}),
                           pk=["season", "season_type", "team_id", "game_id"])
                    log("TeamGameLogs", season, st, scope="all", df=tlogs)
                except Exception as exc:
                    log("TeamGameLogs", season, st, scope="all", status="error", error_msg=str(exc)[:300])
                    print(f"  [SKIP] team logs {season}/{st}: {exc}")
                time.sleep(THROTTLE)

            if not already_done("PlayerGameLogs", season, st, scope="all"):
                try:
                    plogs = safe_call(ep.PlayerGameLogs, season_nullable=season, season_type_nullable=st,
                                      measure_type_player_game_logs_nullable="Base", opp_team_id_nullable=0,
                                      league_id_nullable=LID)
                    if plogs is not None and not plogs.empty:
                        plogs = plogs.copy()
                        plogs["GAME_DATE"] = _iso_dates(plogs["GAME_DATE"])
                    upsert("player_game_logs",
                           rows_from_df(plogs, identity={"season": season, "season_type": st},
                                        id_map={"player_id": "PLAYER_ID", "team_id": "TEAM_ID",
                                                "game_id": "GAME_ID", "game_date": "GAME_DATE",
                                                "matchup": "MATCHUP", "wl": "WL", "min": "MIN"}),
                           pk=["season", "season_type", "player_id", "game_id"])
                    log("PlayerGameLogs", season, st, scope="all", df=plogs)
                except Exception as exc:
                    log("PlayerGameLogs", season, st, scope="all", status="error", error_msg=str(exc)[:300])
                    print(f"  [SKIP] player logs {season}/{st}: {exc}")
                time.sleep(THROTTLE)


# --- Play-by-play -----------------------------------------------------------
def play_by_play(seasons):
    # Enumerate (game_id, season, season_type) from `schedule` (game_type in 2,4,6); resume
    # via ingestion_log. --max-games caps the batch for smoke tests / resumable chunking.
    games = get_game_ids(seasons, game_types=("2", "4", "6"))
    if MAX_GAMES:
        games = games[:MAX_GAMES]
    done = get_done_scopes("PlayByPlayV3")  # one fetch; skip completed games in-memory
    print(f"  {len(games)} games to scrape ({len(done)} already done, skipping)")
    for game_id, g_season, g_stype in games:
        if game_id in done:
            continue
        # One bad game (throttle exhausting BOTH V3 and V2 retries) must not abort a multi-day
        # run — log it as error and continue; the resume retries 'error' games.
        try:
            try:
                df = safe_call(ep.PlayByPlayV3, game_id=game_id)
            except Exception:
                df = safe_call(ep.PlayByPlayV2, game_id=game_id)  # older-season fallback
            # V3 frames are camelCase; the frame may not echo gameId, so set it from the loop var.
            # actionNumber is NOT unique within a game (linked events share it), so key on a
            # per-game chronological event_idx. Stamp season/season_type from the schedule row.
            if df is not None and not df.empty:
                df = df.reset_index(drop=True)
                df["__eidx"] = range(len(df))
            # Slim table: typed columns only, NO JSONB stats (it blows up disk). Keep shot-chart
            # fields (shotResult/shotDistance/shotValue/xLegacy/yLegacy) as typed columns.
            rows = rows_from_df(
                df, identity={"game_id": game_id, "season": g_season, "season_type": g_stype},
                id_map={"event_idx": "__eidx", "action_number": "actionNumber", "period": "period",
                        "clock": "clock", "team_id": "teamId", "team_tricode": "teamTricode",
                        "person_id": "personId", "player_name": "playerName",
                        "action_type": "actionType", "sub_type": "subType",
                        "description": "description", "score_home": "scoreHome",
                        "score_away": "scoreAway", "shot_result": "shotResult",
                        "shot_distance": "shotDistance", "shot_value": "shotValue",
                        "loc_x": "xLegacy", "loc_y": "yLegacy"},
                include_stats=False)
            upsert("play_by_play", rows, pk=["game_id", "event_idx"])
            log("PlayByPlayV3", season=g_season, season_type=g_stype, scope=game_id, df=df)
        except Exception as exc:
            log("PlayByPlayV3", season=g_season, season_type=g_stype, scope=game_id,
                status="error", error_msg=str(exc)[:300])
            print(f"  [SKIP] pbp game {game_id}: {exc}")
        time.sleep(THROTTLE)


# --- Game rotation (on-court stints per player) -----------------------------
def _rotation_frames_via_zenrows(game_id):
    """GameRotation through ZenRows' rotating proxy (throttle bypass). Returns [away_df, home_df]
    with the same columns nba_api yields, or [] if the game genuinely has no rotation data after
    a few attempts (the occasional empty body recovers on a fresh-IP retry)."""
    params = {"GameID": game_id, "LeagueID": LID}
    for _ in range(3):
        try:
            # 30s cap: valid games answer in <25s; genuinely-empty/old games otherwise hang to
            # ZenRows' internal timeout (~60s default) and tie up a worker. Capping bounds the
            # cost of empties (3 x 30s worst case). Slow-but-valid games lost to the cap log as
            # error and are retried on the next resume pass.
            j = stats_json_via_zenrows("gamerotation", params, host=CFG["host"], timeout=30)
            frames = [pd.DataFrame(rs["rowSet"], columns=rs["headers"])
                      for rs in j.get("resultSets", [])]
            if any(len(f) for f in frames):
                return frames
        except Exception:
            pass
        time.sleep(0.3)
    return []


def _persist_rotation(game_id, g_season, g_stype, frames):
    """Upsert away+home rotation frames + log the scope. Main-thread only (no Supabase calls
    from worker threads). Empty frames -> logged as an error scope so a later run retries it."""
    try:
        if not frames:
            raise ValueError("no rotation data")
        for fr in frames:  # away + home rotation frames
            rows = rows_from_df(
                fr, identity={"game_id": game_id, "season": g_season, "season_type": g_stype},
                id_map={"team_id": "TEAM_ID", "person_id": "PERSON_ID",
                        "in_time_real": "IN_TIME_REAL", "out_time_real": "OUT_TIME_REAL",
                        "player_first": "PLAYER_FIRST", "player_last": "PLAYER_LAST",
                        "player_pts": "PLAYER_PTS", "pt_diff": "PT_DIFF", "usg_pct": "USG_PCT"},
                include_stats=False)
            upsert("game_rotation", rows, pk=["game_id", "person_id", "in_time_real"])
        log("GameRotation", season=g_season, season_type=g_stype, scope=game_id,
            df=frames[0] if frames else None)
    except Exception as exc:
        log("GameRotation", season=g_season, season_type=g_stype, scope=game_id,
            status="error", error_msg=str(exc)[:300])
        print(f"  [SKIP] rotation game {game_id}: {exc}")


def game_rotation(seasons):
    # One GameRotation call per game -> each player's in/out elapsed times (stints), for
    # reconstructing on-court lineups. When ZENROWS_API_KEY is set, fetch through ZenRows'
    # rotating proxy (sidesteps NBA's per-IP empty-body throttle). Per-call latency is high
    # (~15s; ZenRows retries NBA internally), so FAN OUT the fetches across ROT_WORKERS threads
    # — the Business plan's 100-concurrency makes this ~6h instead of days. Fetches run in
    # worker threads; upserts/logging stay serial in the main thread via _persist_rotation.
    use_zenrows = bool(os.getenv("ZENROWS_API_KEY"))
    games = get_game_ids(seasons, game_types=("2", "4", "6"))
    if MAX_GAMES:
        games = games[:MAX_GAMES]
    done = get_done_scopes("GameRotation")  # one fetch; skip completed games in-memory
    todo = [(gid, s, st) for (gid, s, st) in games if gid not in done]
    print(f"  {len(games)} games for rotations ({len(done)} done) -> {len(todo)} to fetch"
          f"{f' [ZenRows x{ROT_WORKERS}]' if use_zenrows else ''}")

    if use_zenrows:
        from collections import deque
        window = deque(maxlen=ROT_WINDOW)   # rolling outcomes: 1 = had data, 0 = failed after retries
        n, cool_steps = 0, 0
        for b in range(0, len(todo), ROT_BATCH):
            batch = todo[b:b + ROT_BATCH]
            with ThreadPoolExecutor(max_workers=ROT_WORKERS) as pool:
                futs = {pool.submit(_rotation_frames_via_zenrows, gid): (gid, s, st)
                        for (gid, s, st) in batch}
                for fut in as_completed(futs):
                    gid, s, st = futs[fut]
                    try:
                        frames = fut.result()
                    except Exception:
                        frames = []
                    window.append(1 if frames else 0)
                    _persist_rotation(gid, s, st, frames)
                    n += 1
            recent = sum(window) / len(window) if window else 1.0
            print(f"  ... {n}/{len(todo)} done | rolling success {recent:.0%}", flush=True)
            # circuit-breaker: a full unhealthy window -> escalating cooldown, then re-measure fresh
            if len(window) >= ROT_WINDOW and recent < ROT_BREAKER:
                cool_steps += 1
                cool = min(60 * 2 ** (cool_steps - 1), 1800)   # 60,120,240,... cap 30m
                print(f"  [BREAKER] success {recent:.0%} < {ROT_BREAKER:.0%} -> cooling {cool}s "
                      f"(step {cool_steps}); resumable if killed", flush=True)
                time.sleep(cool)
                window.clear()
            elif recent >= ROT_BREAKER:
                cool_steps = max(0, cool_steps - 1)            # decay escalation as it recovers
    else:
        for game_id, g_season, g_stype in todo:
            try:
                frames = safe_call(ep.GameRotation, game_id=game_id, league_id=LID, _all_frames=True)
            except Exception as exc:
                print(f"  [SKIP] rotation game {game_id}: {exc}")
                frames = []
            _persist_rotation(game_id, g_season, g_stype, frames)
            time.sleep(THROTTLE)  # direct path only; ZenRows fans out instead


# --- Tracking dashboards (Part A: defense / hustle / shot-splits) ------------
def _dash_unit(season, st, ep_name, scope, fetch, table, pk_cols, identity_extra, id_map):
    """One resumable dashboard unit: skip if already ok, fetch (one throttled failure -> log
    error + skip, not abort), upsert to a jsonb-stats table, log. Mirrors the tier2 synergy
    block's resilience. `fetch` is a thunk so each call's differing params stay at the call site."""
    if already_done(ep_name, season, st, scope=scope):
        return
    try:
        df = fetch()
    except Exception as exc:  # one throttled unit must not abort a multi-season backfill
        log(ep_name, season, st, scope=scope, status="error", error_msg=str(exc)[:300])
        print(f"  [SKIP] {ep_name} {season}/{st} {scope}: {exc}")
        time.sleep(THROTTLE)
        return
    rows = rows_from_df(df, identity={"season": season, "season_type": st, **identity_extra},
                        constants={"per_mode": "PerGame"}, id_map=id_map)
    upsert(table, rows, pk=["season", "season_type", *pk_cols, "per_mode"])
    log(ep_name, season, st, scope=scope, df=df)
    time.sleep(THROTTLE)


def dashboards(seasons):
    """Part A tracking dashboards, player + team, PerGame, all covered seasons (RS + Playoffs).
    Defense + shot-splits 2013-14+, hustle 2015-16+. Same resume/throttle discipline as tier2."""
    if not CFG["has_tracking"]:
        return
    for season in seasons:
        yr = _start_year(season)
        for st in SEASON_TYPES:
            # A4 — defense dash (player id col is CLOSE_DEF_PERSON_ID; team via PLAYER_LAST_TEAM_ID)
            if yr >= TRACKING_FIRST_YEAR:
                for cat in DEFENSE_CATEGORIES:
                    _dash_unit(season, st, "LeagueDashPtDefend", f"{cat}:Player",
                               lambda cat=cat: safe_call(ep.LeagueDashPtDefend, season=season,
                                   season_type_all_star=st, defense_category=cat,
                                   per_mode_simple="PerGame", league_id=LID),
                               "pt_defend_player", ["player_id", "defense_category"],
                               {"defense_category": cat},
                               {"player_id": "CLOSE_DEF_PERSON_ID", "team_id": "PLAYER_LAST_TEAM_ID"})
                    _dash_unit(season, st, "LeagueDashPtTeamDefend", cat,
                               lambda cat=cat: safe_call(ep.LeagueDashPtTeamDefend, season=season,
                                   season_type_all_star=st, defense_category=cat,
                                   per_mode_simple="PerGame", league_id=LID),
                               "pt_defend_team", ["team_id", "defense_category"],
                               {"defense_category": cat}, {"team_id": "TEAM_ID"})

            # A5 — hustle (2015-16+; first season partial, skip-empty is automatic via log)
            if yr >= HUSTLE_FIRST_YEAR:
                _dash_unit(season, st, "LeagueHustleStatsPlayer", "all",
                           lambda: safe_call(ep.LeagueHustleStatsPlayer, season=season,
                               season_type_all_star=st, per_mode_time="PerGame", league_id_nullable=LID),
                           "hustle_player", ["player_id"], {},
                           {"player_id": "PLAYER_ID", "team_id": "TEAM_ID"})
                _dash_unit(season, st, "LeagueHustleStatsTeam", "all",
                           lambda: safe_call(ep.LeagueHustleStatsTeam, season=season,
                               season_type_all_star=st, per_mode_time="PerGame", league_id_nullable=LID),
                           "hustle_team", ["team_id"], {}, {"team_id": "TEAM_ID"})

            # A6 — shots by dribble range / A7 — shots by closest-defender range (2013-14+).
            # Same endpoint for both; scope-prefixed so ingestion_log keys don't collide.
            if yr >= TRACKING_FIRST_YEAR:
                for rng in DRIBBLE_RANGES:
                    _dash_unit(season, st, "LeagueDashPlayerPtShot", f"dribble:{rng}:Player",
                               lambda rng=rng: safe_call(ep.LeagueDashPlayerPtShot, season=season,
                                   season_type_all_star=st, per_mode_simple="PerGame", league_id=LID,
                                   team_id_nullable=0, dribble_range_nullable=rng),
                               "pt_shot_dribble_player", ["player_id", "dribble_range"],
                               {"dribble_range": rng},
                               {"player_id": "PLAYER_ID", "team_id": "PLAYER_LAST_TEAM_ID"})
                    _dash_unit(season, st, "LeagueDashTeamPtShot", f"dribble:{rng}:Team",
                               lambda rng=rng: safe_call(ep.LeagueDashTeamPtShot, season=season,
                                   season_type_all_star=st, per_mode_simple="PerGame", league_id=LID,
                                   dribble_range_nullable=rng),
                               "pt_shot_dribble_team", ["team_id", "dribble_range"],
                               {"dribble_range": rng}, {"team_id": "TEAM_ID"})
                for rng in CLOSE_DEF_RANGES:
                    _dash_unit(season, st, "LeagueDashPlayerPtShot", f"defdist:{rng}:Player",
                               lambda rng=rng: safe_call(ep.LeagueDashPlayerPtShot, season=season,
                                   season_type_all_star=st, per_mode_simple="PerGame", league_id=LID,
                                   team_id_nullable=0, close_def_dist_range_nullable=rng),
                               "pt_shot_defender_player", ["player_id", "close_def_dist_range"],
                               {"close_def_dist_range": rng},
                               {"player_id": "PLAYER_ID", "team_id": "PLAYER_LAST_TEAM_ID"})
                    _dash_unit(season, st, "LeagueDashTeamPtShot", f"defdist:{rng}:Team",
                               lambda rng=rng: safe_call(ep.LeagueDashTeamPtShot, season=season,
                                   season_type_all_star=st, per_mode_simple="PerGame", league_id=LID,
                                   close_def_dist_range_nullable=rng),
                               "pt_shot_defender_team", ["team_id", "close_def_dist_range"],
                               {"close_def_dist_range": rng}, {"team_id": "TEAM_ID"})


TIERS = {
    "dims": load_dimensions, "1": tier1, "seed": seed_players,
    "2": tier2, "3": tier3, "dash": dashboards, "pbp": play_by_play, "rotation": game_rotation,
}


def main():
    global MAX_ENTITIES, MAX_GAMES
    p = argparse.ArgumentParser()
    # Defaults follow the active league (NBA 2005-..; WNBA 1997-..). seasons_between parses
    # the leading year, so either 'YYYY' or 'YYYY-YY' works here.
    p.add_argument("--start", default=season_string(CFG, CFG["season_start"]))
    p.add_argument("--end", default=season_string(CFG, CFG["season_end"]))
    p.add_argument("--tier", choices=["all", "dims", "1", "seed", "2", "3", "dash", "pbp", "rotation"],
                   default="all")
    p.add_argument("--max-entities", type=int, default=0,
                   help="cap per-team on/off + per-player passing loops in tier 2 (0 = no cap)")
    p.add_argument("--max-games", type=int, default=0,
                   help="cap games in the play-by-play pass (0 = no cap)")
    args = p.parse_args()
    MAX_ENTITIES, MAX_GAMES = args.max_entities, args.max_games

    print(f"LEAGUE={CFG['league']} host={CFG['host']} schema={CFG['schema']} league_id={LID}")
    patch_nba_session(CFG)  # install curl_cffi session pointed at the league's host
    seasons = seasons_between(args.start, args.end)

    order = (["dims", "1", "seed", "2", "3", "dash", "pbp", "rotation"]
             if args.tier == "all" else [args.tier])
    for name in order:
        print(f"=== Tier {name} : {seasons[0]}..{seasons[-1]} ===")
        TIERS[name](seasons)


if __name__ == "__main__":
    main()
