"""
Dry-run validator for the historical-database column maps.

Does NOT write to Supabase. For one season (default 2024-25, both season types),
it calls each nba_api endpoint that `ingest.py` uses and checks that every SOURCE
column referenced in that endpoint's id_map actually exists in the live DataFrame.

Goal: surface broken/renamed column maps BEFORE a real backfill, and confirm the
loop is cyclically runnable for any season.

Run:
    python dry_run_validate.py --season 2024-25
    python dry_run_validate.py --season 2023-24 --skip-pbp

Exit code 0 = all maps valid, 1 = at least one problem surfaced.
"""

import argparse
import sys
import time
import random

from curl_cffi import requests as cffi_requests
import nba_api.stats.endpoints as ep
from nba_api.stats.static import teams as static_teams
from nba_api.library.http import NBAHTTP

IMPERSONATE = "chrome120"
STATS_HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}
THROTTLE = 0.6

# Results accumulators
RESULTS = []   # (endpoint_scope, status, detail)


def patch():
    """Inject a curl_cffi Chrome-impersonation session into nba_api (the correct way
    for nba_api 1.11.x: set_session + headers — no private-class monkeypatch)."""
    sess = cffi_requests.Session(impersonate=IMPERSONATE)
    NBAHTTP.set_session(sess)
    NBAHTTP.headers = STATS_HEADERS


def call(endpoint_cls, _all_frames=False, _retries=4, **kwargs):
    """Call an endpoint with retry. Returns None on total failure (the validator records a
    FAIL and keeps going — a dry run must surface ALL problems, not abort on the first)."""
    last = None
    for attempt in range(_retries):
        try:
            obj = endpoint_cls(timeout=90, **kwargs)
            frames = obj.get_data_frames()
            return frames if _all_frames else frames[0]
        except Exception as exc:  # noqa: BLE001
            last = exc
            delay = 1.0 * (2 ** attempt) + random.uniform(0, 0.5)
            print(f"    retry {attempt+1}/{_retries} ({endpoint_cls.__name__}): {exc} -> {delay:.1f}s")
            time.sleep(delay)
    RESULTS.append((endpoint_cls.__name__, "FAIL", f"{type(last).__name__}: {last}"))
    print(f"  [FAIL] {endpoint_cls.__name__}: {last}")
    return None


def check_columns(scope, df, sources, frame_label=""):
    """Validate that every source column exists in df. Records a result."""
    label = f"{scope}{(' ' + frame_label) if frame_label else ''}"
    if df is None or df.empty:
        RESULTS.append((label, "EMPTY", f"no rows; columns={list(df.columns) if df is not None else 'None'}"))
        print(f"  [EMPTY] {label}")
        return
    cols = set(df.columns)
    missing = [s for s in sources if s not in cols]
    if missing:
        # show near-miss candidates to make remapping easy
        hint = {m: [c for c in df.columns if m.replace('_', '').lower() in c.replace('_', '').lower()
                    or c.replace('_', '').lower() in m.replace('_', '').lower()] for m in missing}
        RESULTS.append((label, "MISSING", f"missing={missing} | candidates={hint}"))
        print(f"  [MISSING] {label}: {missing}")
        print(f"            candidates: {hint}")
    else:
        RESULTS.append((label, "OK", f"{len(df)} rows"))
        print(f"  [OK] {label} ({len(df)} rows)")


def run(season, season_types, skip_pbp):
    # ---- Dimensions: PlayerIndex ----
    print("\n== Dimensions ==")
    df = call(ep.PlayerIndex, season=season, league_id="00")
    check_columns("PlayerIndex", df, ["PERSON_ID", "PLAYER_FIRST_NAME", "PLAYER_LAST_NAME",
        "PLAYER_SLUG", "POSITION", "HEIGHT", "WEIGHT", "COLLEGE", "COUNTRY",
        "DRAFT_YEAR", "DRAFT_ROUND", "DRAFT_NUMBER", "FROM_YEAR", "TO_YEAR"])
    # COMPLETENESS WARNING: PlayerIndex(season=<past>) returns a broken ~140-row subset
    # (missing stars); only the CURRENT season returns the full ~570 roster. The players
    # dimension should be seeded from player_season_stats PLAYER_IDs, not PlayerIndex alone.
    if df is not None and not df.empty and len(df) < 300:
        RESULTS.append(("PlayerIndex completeness", "WARN",
                        f"only {len(df)} players for {season} — PlayerIndex is unreliable for "
                        f"past seasons; seed `players` from player_season_stats instead"))
        print(f"  [WARN] PlayerIndex returned only {len(df)} players for {season} "
              f"(expected ~500+); unreliable for historical seasons")
    time.sleep(THROTTLE)

    for st in season_types:
        print(f"\n== Tier 1 — {st} ==")
        for m in ["Base", "Advanced", "Misc", "Four Factors"]:
            df = call(ep.LeagueDashTeamStats, season=season, season_type_all_star=st,
                      measure_type_detailed_defense=m, per_mode_detailed="PerGame")
            check_columns(f"LeagueDashTeamStats[{m}]", df, ["TEAM_ID", "TEAM_NAME", "GP", "MIN"])
            time.sleep(THROTTLE)
        for m in ["Base", "Advanced", "Misc"]:
            df = call(ep.LeagueDashPlayerStats, season=season, season_type_all_star=st,
                      measure_type_detailed_defense=m, per_mode_detailed="PerGame",
                      league_id_nullable="00")
            check_columns(f"LeagueDashPlayerStats[{m}]", df,
                          ["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "GP", "MIN"])
            time.sleep(THROTTLE)

    # standings — RS only
    print("\n== Tier 1 — Standings (RS only) ==")
    df = call(ep.LeagueStandings, league_id="00", season=season, season_type="Regular Season")
    check_columns("LeagueStandings", df, ["TeamID", "Conference", "Division",
                                          "WINS", "LOSSES", "WinPCT", "PlayoffRank"])
    time.sleep(THROTTLE)

    # ---- Tier 2 ----
    for st in season_types:
        print(f"\n== Tier 2 — {st} ==")
        df = call(ep.LeagueDashTeamClutch, season=season, season_type_all_star=st,
                  per_mode_detailed="PerGame", measure_type_detailed_defense="Advanced")
        check_columns("LeagueDashTeamClutch", df, ["TEAM_ID"])
        time.sleep(THROTTLE)

        df = call(ep.LeagueDashPlayerClutch, season=season, season_type_all_star=st,
                  per_mode_detailed="PerGame", measure_type_detailed_defense="Advanced")
        check_columns("LeagueDashPlayerClutch", df, ["PLAYER_ID", "TEAM_ID"])
        time.sleep(THROTTLE)

        # LeagueDashPtStats — one representative measure per grain (Drives)
        for pt in ["Drives", "Passing"]:
            for who in ("Player", "Team"):
                df = call(ep.LeagueDashPtStats, season=season, season_type_all_star=st,
                          pt_measure_type=pt, player_or_team=who, per_mode_simple="PerGame")
                src = ["PLAYER_ID", "TEAM_ID"] if who == "Player" else ["TEAM_ID"]
                check_columns(f"LeagueDashPtStats[{pt}:{who}]", df, src)
                time.sleep(THROTTLE)

        # Synergy — one representative play type, both groupings + entities
        for grp in ("offensive", "defensive"):
            for abbr in ("P", "T"):
                ent = "PLAYER_ID" if abbr == "P" else "TEAM_ID"
                df = call(ep.SynergyPlayTypes, league_id="00", season=season,
                          season_type_all_star=st, per_mode_simple="Totals",
                          player_or_team_abbreviation=abbr, type_grouping_nullable=grp,
                          play_type_nullable="Isolation")
                check_columns(f"SynergyPlayTypes[Iso:{grp}:{abbr}]", df, [ent, "TEAM_ID"])
                time.sleep(THROTTLE)

        # TeamPlayerOnOffDetails — one team, validate frame order + VS_PLAYER_ID
        tm = static_teams.get_teams()[0]
        frames = call(ep.TeamPlayerOnOffDetails, team_id=tm["id"], season=season,
                      season_type_all_star=st, per_mode_detailed="Totals",
                      measure_type_detailed_defense="Advanced", _all_frames=True)
        print(f"  TeamPlayerOnOffDetails returned {len(frames)} frames (ingest expects idx 1=OFF, 2=ON)")
        for idx, onoff in ((2, "ON"), (1, "OFF")):
            if len(frames) > idx:
                check_columns("TeamPlayerOnOffDetails", frames[idx], ["VS_PLAYER_ID"],
                              frame_label=f"frame[{idx}]={onoff}")
            else:
                RESULTS.append((f"TeamPlayerOnOffDetails frame[{idx}]={onoff}", "MISSING",
                                f"only {len(frames)} frames returned"))
                print(f"  [MISSING] TeamPlayerOnOffDetails frame[{idx}]={onoff}: only {len(frames)} frames")
        time.sleep(THROTTLE)

        # PlayerDashPtPass — one player, validate frame count + map
        plog = call(ep.LeagueDashPlayerStats, season=season, season_type_all_star=st,
                    measure_type_detailed_defense="Base", per_mode_detailed="PerGame",
                    league_id_nullable="00")
        if plog is not None and not plog.empty:
            pid = int(plog.iloc[0]["PLAYER_ID"])
            frames = call(ep.PlayerDashPtPass, player_id=pid, team_id=0, season=season,
                          season_type_all_star=st, per_mode_simple="PerGame", _all_frames=True)
            print(f"  PlayerDashPtPass(pid={pid}) returned {len(frames)} frames "
                  f"(ingest zips ['made','received'])")
            for i, fr in enumerate(frames):
                check_columns("PlayerDashPtPass", fr, ["TEAM_ID", "PASS_TEAMMATE_PLAYER_ID"],
                              frame_label=f"frame[{i}]")
        time.sleep(THROTTLE)

    # ---- Tier 3 ----
    print("\n== Tier 3 — Schedule + Game Logs ==")
    sched = call(ep.ScheduleLeagueV2, season=season, league_id="00")
    sched_cols = set(sched.columns) if sched is not None else set()
    gid_col = "GAME_ID" if "GAME_ID" in sched_cols else ("gameId" if "gameId" in sched_cols else None)
    print(f"  Schedule game-id column resolved to: {gid_col}")
    # Schedule columns are camelCase + nested (gameDate, homeTeam_teamId, awayTeam_teamId).
    check_columns("ScheduleLeagueV2", sched,
                  [c for c in [gid_col, "gameDate", "homeTeam_teamId", "awayTeam_teamId"] if c])
    if gid_col is None:
        RESULTS.append(("ScheduleLeagueV2 game-id", "MISSING",
                        f"neither GAME_ID nor gameId present; columns={list(sched_cols)}"))
    time.sleep(THROTTLE)

    for st in season_types:
        # *GameLogs endpoints require explicit MeasureType + OpponentTeamID (see ingest.py).
        df = call(ep.TeamGameLogs, season_nullable=season, season_type_nullable=st,
                  measure_type_player_game_logs_nullable="Base", opp_team_id_nullable=0)
        check_columns(f"TeamGameLogs[{st}]", df,
                      ["TEAM_ID", "GAME_ID", "GAME_DATE", "MATCHUP", "WL", "MIN"])
        time.sleep(THROTTLE)
        df = call(ep.PlayerGameLogs, season_nullable=season, season_type_nullable=st,
                  measure_type_player_game_logs_nullable="Base", opp_team_id_nullable=0)
        check_columns(f"PlayerGameLogs[{st}]", df,
                      ["PLAYER_ID", "TEAM_ID", "GAME_ID", "GAME_DATE", "MATCHUP", "WL", "MIN"])
        time.sleep(THROTTLE)

    # ---- PBP ----
    if not skip_pbp:
        print("\n== Tier 3.5 — Play-by-play ==")
        # find a regular-season game id from the schedule
        game_id = None
        if sched is not None and gid_col is not None:
            for gid in sched[gid_col].astype(str):
                if len(gid) > 2 and gid[2] in ("2", "4", "6"):
                    game_id = gid
                    break
        if game_id:
            print(f"  Using game_id={game_id}")
            try:
                df = call(ep.PlayByPlayV3, game_id=game_id)
                tag = "PlayByPlayV3"
            except Exception:
                df = call(ep.PlayByPlayV2, game_id=game_id)
                tag = "PlayByPlayV2(fallback)"
            check_columns(tag, df, ["actionNumber", "period", "clock", "teamId", "personId",
                                    "actionType", "subType", "description", "scoreHome", "scoreAway"])
        else:
            RESULTS.append(("PlayByPlay", "SKIP", "no game_id resolvable from schedule"))
            print("  [SKIP] no game_id resolvable from schedule")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--season", default="2024-25")
    p.add_argument("--skip-pbp", action="store_true")
    p.add_argument("--rs-only", action="store_true")
    args = p.parse_args()

    patch()
    season_types = ["Regular Season"] if args.rs_only else ["Regular Season", "Playoffs"]
    print(f"Dry-run column-map validation for season={args.season}, types={season_types}")

    run(args.season, season_types, args.skip_pbp)

    # ---- Summary ----
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    bad = [r for r in RESULTS if r[1] in ("MISSING", "FAIL")]
    warn = [r for r in RESULTS if r[1] == "WARN"]
    empty = [r for r in RESULTS if r[1] == "EMPTY"]
    ok = [r for r in RESULTS if r[1] == "OK"]
    for label, status, detail in RESULTS:
        if status != "OK":
            print(f"  [{status}] {label}: {detail}")
    print(f"\n  OK={len(ok)}  EMPTY={len(empty)}  WARN={len(warn)}  PROBLEMS={len(bad)}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
