"""
Ingest NBA player-tracking gravity into `player_gravity_tracking`.

Source: stats.nba.com /stats/gravityleaders — a tracking-derived measure of the
defensive attention a player commands, built from per-frame defender positioning.
It is NOT an nba_api endpoint, so this goes through curl_cffi directly rather than
`safe_call`, reusing `nba_session`'s Chrome impersonation and empty-body handling.

COVERAGE: 2025-26 forward only. The endpoint returns nothing for earlier seasons —
confirmed with the user, not inferred from a throttled probe. Everything downstream
(the season-scoped `hexagon_weights` rows) exists because of this limitation.

THROTTLE: stats.nba.com answers a burst of requests with a 200 and an empty body.
That is indistinguishable from "no data" unless you re-request a season you know
works, so this script treats an empty body as retryable and fails loud rather than
writing an empty season.

Usage:
    python fetch_gravity_tracking.py                    # current season
    python fetch_gravity_tracking.py --season 2026-27
    python fetch_gravity_tracking.py --dry-run          # fetch + report, no write

Runs from a residential IP only — NBA blocks datacenter ranges, so this cannot run
on Vercel or hosted CI.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from curl_cffi import requests as cffi_requests

from nba_session import IMPERSONATE, _headers_for
import supabase_io as sio

CURRENT_SEASON = "2025-26"
SEASON_TYPE = "Regular Season"
ENDPOINT = "gravityleaders"
TABLE = "player_gravity_tracking"
PK = ["season", "season_type", "player_id"]

# The endpoint's own field names -> our columns. Splits are the four
# on/off-ball x perimeter/interior gravity scores.
FIELD_MAP = {
    "team_id": "TEAMID",
    "frames": "FRAMES",
    "gravity_score": "GRAVITYSCORE",
    "avg_gravity_score": "AVGGRAVITYSCORE",
    "onball_perimeter_gravity": "ONBALLPERIMETERGRAVITYSCORE",
    "offball_perimeter_gravity": "OFFBALLPERIMETERGRAVITYSCORE",
    "onball_interior_gravity": "ONBALLINTERIORGRAVITYSCORE",
    "offball_interior_gravity": "OFFBALLINTERIORGRAVITYSCORE",
    "games_played": "GAMESPLAYED",
    "minutes": "MINUTES",
}


def fetch_gravity(season: str, season_type: str = SEASON_TYPE, retries: int = 5) -> list[dict]:
    """Fetch the gravity leaderboard. Raises rather than returning an empty season."""
    params = {"LeagueID": "00", "Season": season, "SeasonType": season_type}
    last = None
    for attempt in range(retries):
        # Fresh TLS session per attempt — nba_session.reset_session()'s remedy for
        # the empty-body throttle.
        session = cffi_requests.Session(impersonate=IMPERSONATE)
        try:
            resp = session.get(
                f"https://stats.nba.com/stats/{ENDPOINT}",
                params=params, headers=_headers_for(), timeout=90,
            )
            resp.raise_for_status()
            if not resp.text.strip():
                raise ValueError("empty body (throttled)")
            leaders = json.loads(resp.text).get("leaders", [])
            if not leaders:
                # A real 200 with a real empty list = season genuinely not covered.
                raise RuntimeError(f"{season}: endpoint returned 0 players — season not covered")
            return leaders
        except RuntimeError:
            raise
        except Exception as exc:  # noqa: BLE001 — surfaced after retries
            last = exc
            delay = 2.0 * (2 ** attempt)
            print(f"  retry {attempt + 1}/{retries}: {exc} -> sleeping {delay:.0f}s", flush=True)
            time.sleep(delay)
        finally:
            session.close()
    raise RuntimeError(f"{ENDPOINT} failed for {season} after {retries} attempts") from last


def to_rows(leaders: list[dict], season: str, season_type: str) -> list[dict]:
    rows = []
    for r in leaders:
        row = {
            "season": season,
            "season_type": season_type,
            "player_id": int(r["PLAYERID"]),
            "stats": sio._json_safe(r),
        }
        for col, key in FIELD_MAP.items():
            row[col] = sio._clean(r.get(key))
        rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", default=CURRENT_SEASON)
    ap.add_argument("--season-type", default=SEASON_TYPE)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print(f"Fetching {ENDPOINT} for {args.season} {args.season_type} ...", flush=True)
    leaders = fetch_gravity(args.season, args.season_type)
    rows = to_rows(leaders, args.season, args.season_type)

    top = max(leaders, key=lambda r: r["GRAVITYSCORE"])
    bot = min(leaders, key=lambda r: r["GRAVITYSCORE"])
    print(f"  {len(rows)} players | top {top['FIRSTNAME']} {top['LASTNAME']} "
          f"{top['GRAVITYSCORE']:.2f} | bottom {bot['FIRSTNAME']} {bot['LASTNAME']} "
          f"{bot['GRAVITYSCORE']:.2f}", flush=True)

    if args.dry_run:
        print("  --dry-run: nothing written")
        return 0

    sio.upsert(TABLE, rows, PK)
    sio.log(ENDPOINT, season=args.season, season_type=args.season_type)
    print(f"  upserted {len(rows)} rows into {TABLE}")
    print("  NOTE: run SELECT public.refresh_player_axis_metrics('%s'); to fold this "
          "into the hexagon." % args.season)
    return 0


if __name__ == "__main__":
    sys.exit(main())
