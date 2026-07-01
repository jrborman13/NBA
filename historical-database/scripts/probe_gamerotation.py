"""
Controlled GameRotation sustainability probe (de-risk before a full ZenRows backfill).

The earlier failure was FAN-OUT: 75 concurrent requests tripped NBA's Akamai bot manager and the
damage was cumulative (success stayed depressed even after dropping concurrency). This probe runs at
LOW concurrency over N games and reports the success rate in time-ordered windows. If success stays
flat -> the rate is sustainable and we can scale the backfill. If it declines window-over-window ->
we're re-flagging ourselves and must go slower / cool down / rotate IPs.

A circuit-breaker stops early if a recent window collapses, so we learn the limit cheaply.

Usage: python probe_gamerotation.py [concurrency=3] [n_games=200] [season=2023-24]
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

import supabase_io as s
import nba_session as ns

CONC = int(sys.argv[1]) if len(sys.argv) > 1 else 3
N = int(sys.argv[2]) if len(sys.argv) > 2 else 200
SEASON = sys.argv[3] if len(sys.argv) > 3 else "2023-24"

c = s.client()
# Modern season games are known to HAVE rotation data, so any failure = throttle/Akamai (clean signal).
games = sorted({r["scope"] for r in s._select_all(
    "ingestion_log", "scope",
    lambda q: q.eq("endpoint", "PlayByPlayV3").eq("season", SEASON).eq("status", "ok"),
    order="scope")})[:N]
print(f"probing {len(games)} {SEASON} games @ concurrency {CONC}\n")


def fetch(g):
    t = time.time()
    try:
        j = ns.stats_json_via_zenrows("gamerotation", {"GameID": g, "LeagueID": "00"}, timeout=30)
        n = sum(len(rs.get("rowSet", [])) for rs in j["resultSets"])
        return (1 if n > 0 else 0, time.time() - t)
    except Exception:
        return (0, time.time() - t)


results, lats = [], []
t0 = time.time()
pool = ThreadPoolExecutor(max_workers=CONC)
futs = {pool.submit(fetch, g): g for g in games}
tripped = False
for fut in as_completed(futs):
    ok, lat = fut.result()
    results.append(ok)
    lats.append(lat)
    # circuit-breaker: severe collapse in the most recent 40 (>70% failure)
    if len(results) >= 40 and sum(results[-40:]) / 40 < 0.30:
        print(f"!! CIRCUIT BREAKER at {len(results)} games: recent-40 success "
              f"{sum(results[-40:])}/40 — stopping to avoid digging in deeper\n")
        tripped = True
        pool.shutdown(wait=False, cancel_futures=True)
        break
pool.shutdown(wait=True)

print("success by completion-order window (degradation check):")
for i in range(0, len(results), 50):
    w = results[i:i + 50]
    print(f"  games {i + 1:>3}-{i + len(w):<3}: {sum(w):>2}/{len(w)} ok ({sum(w) / len(w) * 100:.0f}%)")
avg_lat = sum(lats) / len(lats) if lats else 0
print(f"\nTOTAL: {sum(results)}/{len(results)} ok ({sum(results) / len(results) * 100:.0f}%) "
      f"| {time.time() - t0:.0f}s | {avg_lat:.1f}s/call avg | conc={CONC} | breaker={'TRIPPED' if tripped else 'ok'}")
