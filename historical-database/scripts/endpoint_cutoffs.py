"""
Endpoint historical cut-off probe.

For each season in a spread across NBA eras, call every endpoint `ingest.py` uses ONCE
(Regular Season) and record status + row count. Output: a per-endpoint cut-off summary
(earliest season that returns data) + a full season×endpoint matrix.

No Supabase writes. Use this to learn where each endpoint's data begins BEFORE a full
backfill, so the orchestrator can skip known-empty (endpoint, season) units cleanly.

Run:
    python endpoint_cutoffs.py                       # default era spread
    python endpoint_cutoffs.py --seasons 2015-16 2014-15 2013-14
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
    "Referer": "https://www.nba.com/", "Origin": "https://www.nba.com",
    "x-nba-stats-origin": "stats", "x-nba-stats-token": "true",
}
THROTTLE = 0.6

DEFAULT_SEASONS = ["2024-25", "2019-20", "2016-17", "2015-16", "2014-15",
                   "2013-14", "2012-13", "2010-11", "2007-08", "2005-06"]

# matrix[endpoint][season] = "OK:n" | "EMPTY" | "FAIL"
MATRIX = {}
ENDPOINT_ORDER = []


def patch():
    NBAHTTP.set_session(cffi_requests.Session(impersonate=IMPERSONATE))
    NBAHTTP.headers = STATS_HEADERS


def probe(name, fn, season):
    """Run one probe fn -> a DataFrame (or None). Record OK:n / EMPTY / FAIL:<reason>."""
    if name not in MATRIX:
        MATRIX[name] = {}
        ENDPOINT_ORDER.append(name)
    last = None
    for attempt in range(3):
        try:
            df = fn()
            if df is None or (hasattr(df, "empty") and df.empty):
                MATRIX[name][season] = "EMPTY"
                print(f"    {name:34s} {season}  EMPTY")
            else:
                MATRIX[name][season] = f"OK:{len(df)}"
                print(f"    {name:34s} {season}  OK ({len(df)} rows)")
            return df
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.0 * (2 ** attempt) + random.uniform(0, 0.4))
    short = str(last).split("\n")[0][:60]
    MATRIX[name][season] = f"FAIL:{short}"
    print(f"    {name:34s} {season}  FAIL ({short})")
    return None


def run_season_new(season):
    """Probe ONLY the new tracking dashboards (defense / hustle / shot-splits) added for the
    dashboards-ingest build. One category each is enough to find the season floor. --new-only."""
    print(f"\n=== {season} (Regular Season) [new endpoints] ===")
    st = "Regular Season"
    probe("LeagueDashPtDefend[Overall]", lambda: ep.LeagueDashPtDefend(
        season=season, season_type_all_star=st, defense_category="Overall",
        per_mode_simple="PerGame", league_id="00", timeout=90).get_data_frames()[0], season)
    time.sleep(THROTTLE)
    probe("LeagueDashPtTeamDefend[Overall]", lambda: ep.LeagueDashPtTeamDefend(
        season=season, season_type_all_star=st, defense_category="Overall",
        per_mode_simple="PerGame", league_id="00", timeout=90).get_data_frames()[0], season)
    time.sleep(THROTTLE)
    probe("LeagueHustleStatsPlayer", lambda: ep.LeagueHustleStatsPlayer(
        season=season, season_type_all_star=st, per_mode_time="PerGame",
        league_id_nullable="00", timeout=90).get_data_frames()[0], season)
    time.sleep(THROTTLE)
    probe("LeagueHustleStatsTeam", lambda: ep.LeagueHustleStatsTeam(
        season=season, season_type_all_star=st, per_mode_time="PerGame",
        league_id_nullable="00", timeout=90).get_data_frames()[0], season)
    time.sleep(THROTTLE)
    probe("LeagueDashPlayerPtShot", lambda: ep.LeagueDashPlayerPtShot(
        season=season, season_type_all_star=st, per_mode_simple="PerGame",
        league_id="00", team_id_nullable=0, timeout=90).get_data_frames()[0], season)
    time.sleep(THROTTLE)
    probe("LeagueDashTeamPtShot", lambda: ep.LeagueDashTeamPtShot(
        season=season, season_type_all_star=st, per_mode_simple="PerGame",
        league_id="00", timeout=90).get_data_frames()[0], season)
    time.sleep(THROTTLE)


def run_season(season):
    print(f"\n=== {season} (Regular Season) ===")
    st = "Regular Season"
    tm0 = static_teams.get_teams()[0]["id"]

    probe("PlayerIndex", lambda: ep.PlayerIndex(
        season=season, league_id="00", timeout=90).get_data_frames()[0], season)
    time.sleep(THROTTLE)

    for m in ["Base", "Advanced", "Misc", "Four Factors"]:
        probe(f"LeagueDashTeamStats[{m}]", lambda m=m: ep.LeagueDashTeamStats(
            season=season, season_type_all_star=st, measure_type_detailed_defense=m,
            per_mode_detailed="PerGame", timeout=90).get_data_frames()[0], season)
        time.sleep(THROTTLE)

    pl_base = None
    for m in ["Base", "Advanced", "Misc"]:
        df = probe(f"LeagueDashPlayerStats[{m}]", lambda m=m: ep.LeagueDashPlayerStats(
            season=season, season_type_all_star=st, measure_type_detailed_defense=m,
            per_mode_detailed="PerGame", league_id_nullable="00", timeout=90).get_data_frames()[0], season)
        if m == "Base":
            pl_base = df
        time.sleep(THROTTLE)

    probe("LeagueStandings", lambda: ep.LeagueStandings(
        league_id="00", season=season, season_type="Regular Season", timeout=90).get_data_frames()[0], season)
    time.sleep(THROTTLE)

    probe("LeagueDashTeamClutch", lambda: ep.LeagueDashTeamClutch(
        season=season, season_type_all_star=st, per_mode_detailed="PerGame",
        measure_type_detailed_defense="Advanced", timeout=90).get_data_frames()[0], season)
    time.sleep(THROTTLE)
    probe("LeagueDashPlayerClutch", lambda: ep.LeagueDashPlayerClutch(
        season=season, season_type_all_star=st, per_mode_detailed="PerGame",
        measure_type_detailed_defense="Advanced", timeout=90).get_data_frames()[0], season)
    time.sleep(THROTTLE)

    probe("LeagueDashPtStats[Drives]", lambda: ep.LeagueDashPtStats(
        season=season, season_type_all_star=st, pt_measure_type="Drives",
        player_or_team="Player", per_mode_simple="PerGame", timeout=90).get_data_frames()[0], season)
    time.sleep(THROTTLE)

    probe("SynergyPlayTypes[Iso]", lambda: ep.SynergyPlayTypes(
        league_id="00", season=season, season_type_all_star=st, per_mode_simple="Totals",
        player_or_team_abbreviation="T", type_grouping_nullable="offensive",
        play_type_nullable="Isolation", timeout=90).get_data_frames()[0], season)
    time.sleep(THROTTLE)

    probe("TeamPlayerOnOffDetails", lambda: ep.TeamPlayerOnOffDetails(
        team_id=tm0, season=season, season_type_all_star=st, per_mode_detailed="Totals",
        measure_type_detailed_defense="Advanced", timeout=90).get_data_frames()[0], season)
    time.sleep(THROTTLE)

    pid = None
    if pl_base is not None and not pl_base.empty and "PLAYER_ID" in pl_base.columns:
        pid = int(pl_base.iloc[0]["PLAYER_ID"])
    if pid:
        probe("PlayerDashPtPass", lambda: ep.PlayerDashPtPass(
            player_id=pid, team_id=0, season=season, season_type_all_star=st,
            per_mode_simple="PerGame", timeout=90).get_data_frames()[0], season)
        time.sleep(THROTTLE)
    else:
        MATRIX.setdefault("PlayerDashPtPass", {})[season] = "SKIP:no pid"
        if "PlayerDashPtPass" not in ENDPOINT_ORDER:
            ENDPOINT_ORDER.append("PlayerDashPtPass")

    sched = probe("ScheduleLeagueV2", lambda: ep.ScheduleLeagueV2(
        season=season, league_id="00", timeout=90).get_data_frames()[0], season)
    time.sleep(THROTTLE)

    probe("TeamGameLogs", lambda: ep.TeamGameLogs(
        season_nullable=season, season_type_nullable=st,
        measure_type_player_game_logs_nullable="Base", opp_team_id_nullable=0,
        timeout=90).get_data_frames()[0], season)
    time.sleep(THROTTLE)
    probe("PlayerGameLogs", lambda: ep.PlayerGameLogs(
        season_nullable=season, season_type_nullable=st,
        measure_type_player_game_logs_nullable="Base", opp_team_id_nullable=0,
        timeout=90).get_data_frames()[0], season)
    time.sleep(THROTTLE)

    # PBP: resolve a regular-season game id from the schedule, try V3 then V2
    gid = None
    if sched is not None and not sched.empty:
        gcol = "GAME_ID" if "GAME_ID" in sched.columns else ("gameId" if "gameId" in sched.columns else None)
        if gcol:
            for g in sched[gcol].astype(str):
                if len(g) > 2 and g[2] == "2":
                    gid = g
                    break
    if gid:
        v3 = probe("PlayByPlayV3", lambda: ep.PlayByPlayV3(
            game_id=gid, timeout=90).get_data_frames()[0], season)
        time.sleep(THROTTLE)
        if v3 is None or (hasattr(v3, "empty") and (v3 is None or v3.empty)):
            probe("PlayByPlayV2", lambda: ep.PlayByPlayV2(
                game_id=gid, timeout=90).get_data_frames()[0], season)
            time.sleep(THROTTLE)
    else:
        MATRIX.setdefault("PlayByPlayV3", {})[season] = "SKIP:no gid"
        if "PlayByPlayV3" not in ENDPOINT_ORDER:
            ENDPOINT_ORDER.append("PlayByPlayV3")


def summarize(seasons):
    print("\n" + "=" * 90)
    print("CUT-OFF SUMMARY (earliest season returning data, scanning oldest→newest)")
    print("=" * 90)
    asc = sorted(seasons, key=lambda s: int(s[:4]))
    for name in ENDPOINT_ORDER:
        row = MATRIX.get(name, {})
        earliest = None
        for s in asc:
            v = row.get(s, "")
            if v.startswith("OK"):
                earliest = s
                break
        statuses = [row.get(s, "-").split(":")[0] for s in asc]
        empties = [s for s in asc if row.get(s, "").startswith("EMPTY")]
        fails = [s for s in asc if row.get(s, "").startswith("FAIL")]
        note = f"earliest OK: {earliest or 'NONE'}"
        if empties:
            note += f" | empty in: {','.join(empties)}"
        if fails:
            note += f" | FAIL in: {','.join(fails)}"
        print(f"  {name:34s} {note}")

    print("\n" + "=" * 90)
    print("FULL MATRIX (newest→oldest)")
    print("=" * 90)
    hdr = "  {:34s}".format("endpoint") + "".join(f"{s:>10s}" for s in seasons)
    print(hdr)
    for name in ENDPOINT_ORDER:
        row = MATRIX.get(name, {})
        cells = "".join(f"{row.get(s,'-'):>10s}"[:10] for s in seasons)
        print(f"  {name:34s}{cells}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seasons", nargs="*", default=DEFAULT_SEASONS)
    p.add_argument("--new-only", action="store_true",
                   help="probe ONLY the new tracking dashboards (defense/hustle/shot-splits)")
    args = p.parse_args()
    patch()
    runner = run_season_new if args.new_only else run_season
    print(f"Probing {'NEW ' if args.new_only else ''}endpoint cut-offs across "
          f"{len(args.seasons)} seasons: {args.seasons}")
    for s in args.seasons:
        runner(s)
    summarize(args.seasons)
    # exit 0 always — this is an informational probe, not a pass/fail gate
    sys.exit(0)


if __name__ == "__main__":
    main()
