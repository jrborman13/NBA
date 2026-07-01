"""
WNBA dry-run column-map validator (no DB writes).

Mirrors dry_run_validate.py but targets the WNBA: stats.wnba.com host, league_id='10',
single-year seasons. Validates that every SOURCE column the ingest id_maps reference exists
in the live WNBA frames, and surfaces which endpoints are unavailable for the WNBA.

Run:  python wnba_dry_run.py --season 2024
"""

import argparse
import sys
import time

from league import WNBA, season_string
from nba_session import patch_nba_session, safe_call
import nba_api.stats.endpoints as ep

LID = WNBA["league_id"]   # '10'
RESULTS = []


def check(scope, df, sources, frame_label=""):
    label = f"{scope}{(' ' + frame_label) if frame_label else ''}"
    if df is None or (hasattr(df, "empty") and df.empty):
        RESULTS.append((label, "EMPTY", "no rows"))
        print(f"  [EMPTY] {label}")
        return
    missing = [s for s in sources if s not in set(df.columns)]
    if missing:
        cand = {m: [c for c in df.columns if m.replace('_', '').lower() in c.replace('_', '').lower()
                    or c.replace('_', '').lower() in m.replace('_', '').lower()] for m in missing}
        RESULTS.append((label, "MISSING", f"missing={missing} candidates={cand}"))
        print(f"  [MISSING] {label}: {missing} | candidates {cand}")
    else:
        RESULTS.append((label, "OK", f"{len(df)} rows"))
        print(f"  [OK] {label} ({len(df)} rows)")


def call(cls, **kw):
    try:
        return safe_call(cls, _retries=3, **kw)
    except Exception as exc:  # noqa: BLE001
        RESULTS.append((cls.__name__, "FAIL", str(exc).split(chr(10))[0][:70]))
        print(f"  [FAIL] {cls.__name__}: {str(exc).split(chr(10))[0][:70]}")
        return None


def run(season):
    st = "Regular Season"
    print(f"\n== Dimensions ==")
    check("PlayerIndex", call(ep.PlayerIndex, season=season, league_id=LID),
          ["PERSON_ID", "PLAYER_FIRST_NAME", "PLAYER_LAST_NAME", "POSITION", "HEIGHT", "TEAM_ID"])
    time.sleep(0.6)

    print("== Tier 1 ==")
    for m in ["Base", "Advanced", "Misc", "Four Factors"]:
        check(f"LeagueDashTeamStats[{m}]",
              call(ep.LeagueDashTeamStats, season=season, season_type_all_star=st,
                   measure_type_detailed_defense=m, per_mode_detailed="PerGame", league_id_nullable=LID),
              ["TEAM_ID", "TEAM_NAME", "GP", "MIN"])
        time.sleep(0.6)
    for m in ["Base", "Advanced", "Misc"]:
        check(f"LeagueDashPlayerStats[{m}]",
              call(ep.LeagueDashPlayerStats, season=season, season_type_all_star=st,
                   measure_type_detailed_defense=m, per_mode_detailed="PerGame", league_id_nullable=LID),
              ["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "GP", "MIN"])
        time.sleep(0.6)
    # WNBA: LeagueStandings (V1) returns empty resultSets; LeagueStandingsV3 works (same cols).
    check("LeagueStandingsV3", call(ep.LeagueStandingsV3, league_id=LID, season=season, season_type="Regular Season"),
          ["TeamID", "Conference", "Division", "WINS", "LOSSES", "WinPCT"])
    time.sleep(0.6)

    print("== Tier 2 ==")
    check("LeagueDashTeamClutch", call(ep.LeagueDashTeamClutch, season=season, season_type_all_star=st,
          per_mode_detailed="PerGame", measure_type_detailed_defense="Advanced", league_id_nullable=LID), ["TEAM_ID"])
    time.sleep(0.6)
    check("LeagueDashPlayerClutch", call(ep.LeagueDashPlayerClutch, season=season, season_type_all_star=st,
          per_mode_detailed="PerGame", measure_type_detailed_defense="Advanced", league_id_nullable=LID),
          ["PLAYER_ID", "TEAM_ID"])
    time.sleep(0.6)
    check("LeagueDashPtStats[Drives]", call(ep.LeagueDashPtStats, season=season, season_type_all_star=st,
          pt_measure_type="Drives", player_or_team="Player", per_mode_simple="PerGame", league_id_nullable=LID),
          ["PLAYER_ID", "TEAM_ID"])
    time.sleep(0.6)
    check("SynergyPlayTypes[Iso]", call(ep.SynergyPlayTypes, league_id=LID, season=season,
          season_type_all_star=st, per_mode_simple="Totals", player_or_team_abbreviation="P",
          type_grouping_nullable="offensive", play_type_nullable="Isolation"), ["PLAYER_ID", "TEAM_ID"])
    time.sleep(0.6)
    # on/off — need a WNBA team_id; pull one from team stats
    tdf = call(ep.LeagueDashTeamStats, season=season, season_type_all_star=st,
               measure_type_detailed_defense="Base", per_mode_detailed="PerGame", league_id_nullable=LID)
    if tdf is not None and not tdf.empty:
        tid = int(tdf.iloc[0]["TEAM_ID"])
        frames = call(ep.TeamPlayerOnOffDetails, team_id=tid, season=season, season_type_all_star=st,
                      per_mode_detailed="Totals", measure_type_detailed_defense="Advanced",
                      league_id_nullable=LID, _all_frames=True)
        if frames and len(frames) > 2:
            check("TeamPlayerOnOffDetails", frames[2], ["VS_PLAYER_ID"], frame_label="frame[2]=ON")
        time.sleep(0.6)
        pdf = call(ep.LeagueDashPlayerStats, season=season, season_type_all_star=st,
                   measure_type_detailed_defense="Base", per_mode_detailed="PerGame", league_id_nullable=LID)
        if pdf is not None and not pdf.empty:
            pid = int(pdf.iloc[0]["PLAYER_ID"])
            frames = call(ep.PlayerDashPtPass, player_id=pid, team_id=0, season=season,
                          season_type_all_star=st, per_mode_simple="PerGame", _all_frames=True)
            if frames:
                check("PlayerDashPtPass", frames[0], ["TEAM_ID", "PASS_TEAMMATE_PLAYER_ID"])
            time.sleep(0.6)

    print("== Tier 3 ==")
    sched = call(ep.ScheduleLeagueV2, season=season, league_id=LID)
    gid_col = "gameId" if (sched is not None and "gameId" in sched.columns) else "GAME_ID"
    check("ScheduleLeagueV2", sched, [gid_col, "gameDate", "homeTeam_teamId", "awayTeam_teamId"])
    time.sleep(0.6)
    for cls, extra in [(ep.TeamGameLogs, ["TEAM_ID"]), (ep.PlayerGameLogs, ["PLAYER_ID", "TEAM_ID"])]:
        check(cls.__name__, call(cls, season_nullable=season, season_type_nullable=st,
              measure_type_player_game_logs_nullable="Base", opp_team_id_nullable=0, league_id_nullable=LID),
              extra + ["GAME_ID", "GAME_DATE", "MATCHUP", "WL", "MIN"])
        time.sleep(0.6)
    # PBP + rotation on one WNBA game from the schedule
    gid = None
    if sched is not None and not sched.empty:
        for g in sched[gid_col].astype(str):
            if len(g) > 2 and g[2] == "2":
                gid = g; break
    if gid:
        check("PlayByPlayV3", call(ep.PlayByPlayV3, game_id=gid),
              ["actionNumber", "period", "clock", "teamId", "personId", "actionType", "shotResult", "xLegacy"])
        time.sleep(0.6)
        rfr = call(ep.GameRotation, game_id=gid, league_id=LID, _all_frames=True)
        if rfr:
            check("GameRotation", rfr[0], ["TEAM_ID", "PERSON_ID", "IN_TIME_REAL", "OUT_TIME_REAL"])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--season", default="2024")
    args = p.parse_args()
    patch_nba_session(WNBA)
    print(f"WNBA dry-run validation, season={args.season}, league_id={LID}, host={WNBA['host']}")
    run(args.season)
    print("\n" + "=" * 64 + "\nSUMMARY")
    bad = [r for r in RESULTS if r[1] in ("MISSING", "FAIL")]
    for label, status, detail in RESULTS:
        if status != "OK":
            print(f"  [{status}] {label}: {detail}")
    ok = sum(1 for r in RESULTS if r[1] == "OK")
    empty = sum(1 for r in RESULTS if r[1] == "EMPTY")
    print(f"\n  OK={ok}  EMPTY={empty}  PROBLEMS={len(bad)}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
