"""
Nightly CURRENT-SEASON warehouse refresh — run locally (curl_cffi reaches stats.nba.com; the
Supabase edge runtime cannot). The historical backfill is one-time + resumable via `already_done`;
this wrapper forces a re-fetch of the in-progress season by clearing that season's `ingestion_log`
rows for the tier's endpoints, then re-running the loader tier from ingest.py.

Cron example (6:10 AM CT, after stats.nba.com has the prior night's games):
    10 6 * * *  cd /path/to/NBA/historical-database/scripts && \
                /path/to/venv311/bin/python refresh_current_season.py >> /tmp/nba_refresh.log 2>&1

Default refreshes the `dash` tier (the defense/hustle/shot-split dashboards added 2026-06-28).
Pass --tier 2 to also refresh the other tracking/synergy/on-off tables, or --season to override.
"""

import argparse
from datetime import date

from dotenv import load_dotenv
load_dotenv()

import ingest
from league import get_league
from nba_session import patch_nba_session
from supabase_io import client

# Endpoints whose current-season ingestion_log must be cleared so the tier re-fetches instead of
# skipping. Keyed by tier. (Extend if a tier's endpoint set grows.)
TIER_ENDPOINTS = {
    "dash": ["LeagueDashPtDefend", "LeagueDashPtTeamDefend",
             "LeagueHustleStatsPlayer", "LeagueHustleStatsTeam",
             "LeagueDashPlayerPtShot", "LeagueDashTeamPtShot"],
}


def current_season() -> str:
    """NBA season label 'YYYY-YY'. The season rolls over in October."""
    t = date.today()
    start = t.year if t.month >= 10 else t.year - 1
    return f"{start}-{str(start + 1)[2:]}"


def _clear_log(season: str, endpoints: list[str]):
    """Delete this season's ingestion_log rows for the given endpoints (all season_types/scopes)
    so already_done() returns False and the loader re-fetches the live current-season numbers."""
    for ep_name in endpoints:
        client().table("ingestion_log").delete().eq("endpoint", ep_name).eq("season", season).execute()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--season", default=current_season())
    p.add_argument("--tier", default="dash", choices=list(TIER_ENDPOINTS))
    args = p.parse_args()

    cfg = get_league()
    patch_nba_session(cfg)
    print(f"[refresh_current_season] tier={args.tier} season={args.season}")
    _clear_log(args.season, TIER_ENDPOINTS[args.tier])
    ingest.TIERS[args.tier]([args.season])
    print(f"[refresh_current_season] done {args.season}")


if __name__ == "__main__":
    main()
