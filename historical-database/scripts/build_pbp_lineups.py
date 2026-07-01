"""
Reconstruct on-court lineups from play_by_play (no scraping) and write per-player stints.

GameRotation (stats.nba.com) is Akamai-blocked under bulk load, so instead we derive the same
on-court information from the PBP we already hold. Substitution rows give the OUT player by
person_id and the IN player by last name in the description ("SUB: <IN> FOR <OUT>"); per-period
starters are inferred from who acts (or is subbed out) before being subbed in that period — a
heuristic validated at 100% on a modern game and ~94% across a mixed ground-truth sample vs the
523 games where GameRotation did get through.

Output: pbp_lineup_stint (game_id, team_id, person_id, period, in/out elapsed + clock). Lineups
at any event = stints whose [in_elapsed, out_elapsed) contains the event's elapsed time.

Usage:
  python build_pbp_lineups.py --season 2025-26 --validate         # consistency report, no writes
  python build_pbp_lineups.py --season 2025-26 --validate --max-games 20
  python build_pbp_lineups.py --season 2025-26 --write            # upsert stints
"""
import argparse
import re
import sys
import unicodedata
from collections import defaultdict

sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

import supabase_io as s
from supabase_io import upsert, log

SUB_RE = re.compile(r"SUB:\s*(.+?)\s+FOR\s+(.+)")
CLOCK_RE = re.compile(r"PT(\d+)M([\d.]+)S")
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
# Umlauts are inconsistent across sources: German spells them out (PBP 'Pöltl' vs game-log
# 'Poeltl' = ö->oe) while French/other use a bare diaeresis (PBP 'Salaün' vs game-log 'Salaun'
# = ü->u). No single rule works, so variants() emits BOTH the stripped and spelled-out forms and
# matching succeeds if either aligns.
UMLAUT = str.maketrans({"ö": "oe", "ä": "ae", "ü": "ue", "ß": "ss", "ø": "oe", "å": "aa"})


def _strip(x):
    # NFKD-unaccent, drop non-ASCII, then remove punctuation (keep a-z 0-9 space). Collapses
    # apostrophe variants ("N'Dong" curly U+2019 vs straight ' -> "ndong") and hyphens
    # ("Seung-Jin"/"Whiting-Raymond" -> "seungjin"/"whitingraymond"). Input is already lowercased.
    x = "".join(ch for ch in unicodedata.normalize("NFKD", x) if ord(ch) < 128)
    return re.sub(r"[^a-z0-9 ]+", "", x).strip()


def norm(x):
    """Primary key: unaccent + lowercase, so 'Dončić'=='Doncic', 'Salaün'=='Salaun'."""
    return _strip((x or "").lower())


def variants(x):
    """{stripped, umlaut-spelled} so 'Pöltl' -> {'poltl','poeltl'} matches game-log 'Poeltl',
    and 'Salaün' -> {'salaun','salaeun'} matches game-log 'Salaun'."""
    x = (x or "").lower()
    return {_strip(x), _strip(x.translate(UMLAUT))}


def tokenize(name):
    """Unaccented word tokens: 'Jaren Jackson Jr.' -> ['jaren','jackson','jr']."""
    return [norm(t) for t in (name or "").replace(".", " ").split() if norm(t)]


def last_key(toks):
    """The last non-suffix token (the surname) used to index the roster."""
    core = [t for t in toks if t not in SUFFIXES]
    return core[-1] if core else (toks[-1] if toks else "")


def prefix_match(in_toks, roster_toks):
    """True if every IN token prefix-matches a DISTINCT roster token. Handles initials ('g' ->
    'giannis'), multi-char prefixes ('jay' -> 'jaylen'), suffixes ('jr' -> 'jr'), and diacritics
    (already unaccented). 'Jackson Jr.' matches 'Jaren Jackson Jr.' but not 'GG Jackson II'."""
    used = set()
    for it in in_toks:
        hit = next((i for i, rt in enumerate(roster_toks)
                    if i not in used and (rt.startswith(it) or it.startswith(rt))), None)
        if hit is None:
            return False
        used.add(hit)
    return True


def build_resolver(c, game_id, events):
    """Map a substitution IN display-name -> person_id, per team. Two tiers:
      1. EXACT match on the PBP `player_name` of an acting event — this is each player's canonical
         sub-name (subs and actions share one convention), so 'Jackson' -> GG, 'Jackson Jr.' ->
         Jaren, 'Jay. Williams' -> Jaylen, diacritics, all resolve exactly.
      2. Fallback for players who never act in PBP: token-prefix match against the player_game_logs
         roster (full names). Returns None only when genuinely ambiguous."""
    exact = defaultdict(dict)  # team -> name-variant -> pid
    for e in events:
        if not e["team_id"]:
            continue
        if e["person_id"] and e["player_name"]:
            for v in variants(e["player_name"]):
                exact[e["team_id"]].setdefault(v, e["person_id"])
        # A substitution's OUT player gives a HISTORICAL description-name ("SUB: A FOR Kanter")
        # bound to a real person_id (e["person_id"] = the OUT player). The structured player_name
        # /game-logs carry a player's CURRENT name (Kanter -> "Freedom", Pendergraph -> "Ayres"),
        # but descriptions keep the name used at the time -> this is the only bridge for renames.
        if e["action_type"] == "Substitution" and e["person_id"]:
            m = SUB_RE.match(e["description"] or "")
            if m:
                for v in variants(m.group(2).strip()):
                    exact[e["team_id"]].setdefault(v, e["person_id"])

    roster = defaultdict(lambda: defaultdict(list))  # team -> surname -> [(tokens, pid)]
    rows = (_t(c, "player_game_logs").select("player_id,team_id,stats")
            .eq("game_id", game_id).execute().data)
    for r in rows:
        toks = tokenize((r.get("stats") or {}).get("PLAYER_NAME") or "")
        if toks:
            roster[r["team_id"]][last_key(toks)].append((toks, r["player_id"]))

    def resolve(team_id, in_name, exclude=frozenset()):
        # `exclude` = person_ids currently on the floor; a player can't sub into a game they're
        # already in, so when a name is ambiguous prefer the candidate who is OFF the floor.
        em = exact.get(team_id, {})
        for v in variants(in_name):
            if v in em and em[v] not in exclude:
                return em[v]              # high-confidence exact, and not contradicted by state
        in_toks = tokenize(in_name)
        cands = roster.get(team_id, {}).get(last_key(in_toks), [])
        ids = {pid for _, pid in cands}
        match = {pid for toks, pid in cands if prefix_match(in_toks, toks)} or ids
        off = match - set(exclude)
        if len(off) == 1:
            return next(iter(off))        # unique once we drop on-floor players
        if len(match) == 1:
            return next(iter(match))
        # last resort: an exact hit even if it looked contradicted (rare data quirk)
        for v in variants(in_name):
            if v in em:
                return em[v]
        return None
    return resolve


REG_SEC = 720   # regulation period length: 720 (NBA 12-min) or 600 (WNBA 10-min); set per --league


def period_len(p):
    """Period length in seconds: REG_SEC in regulation, 300 (5 min) in OT (period > 4)."""
    return REG_SEC if p <= 4 else 300


def clock_remaining(clk):
    m = CLOCK_RE.match(clk or "")
    return int(m.group(1)) * 60 + float(m.group(2)) if m else None


def elapsed(period, clk):
    """Game-elapsed seconds at this period+clock (clock counts DOWN within a period)."""
    rem = clock_remaining(clk)
    if rem is None:
        return None
    return sum(period_len(p) for p in range(1, period)) + (period_len(period) - rem)


def period_bounds(period):
    start = sum(period_len(p) for p in range(1, period))
    return start, start + period_len(period)


def _t(c, name):
    """Schema-aware table handle: wnba schema when supabase_io.SCHEMA is set, else public (NBA)."""
    return c.schema(s.SCHEMA).table(name) if s.SCHEMA else c.table(name)


def fetch_events(c, game_id):
    """All PBP events for a game, ordered. ~500 rows/game, under the 1000 page cap."""
    return (_t(c, "play_by_play")
            .select("event_idx,period,clock,person_id,player_name,team_id,action_type,"
                    "sub_type,description,season,season_type")
            .eq("game_id", game_id).order("event_idx").execute().data)


def reconstruct(events, resolve):
    """Return (stints, problems). Single capped pass per period: a player is placed on the floor
    the first time they act or are subbed OUT (revealing a tip-off starter); the floor is capped at
    5; substitution IN-names resolve against who is currently on court (a player can't enter a game
    they're already in). Quiet starters who play a full period without acting are filled from the
    prior period's closing lineup. problems = (period, team, why) consistency violations."""
    teams = {e["team_id"] for e in events if e["team_id"]}
    stints, problems = [], []
    meta = events[0] if events else {}
    prev_on = {tid: set() for tid in teams}  # on-floor at the end of the previous period
    for period in sorted({e["period"] for e in events if e["period"]}):
        pev = [e for e in events if e["period"] == period]
        p_start, p_end = period_bounds(period)
        start_clk = f"PT{period_len(period) // 60:02d}M00.00S"
        on = {tid: {} for tid in teams}          # pid -> (in_elapsed, in_clock)
        subbed_in = {tid: set() for tid in teams}
        quiet = {tid: set() for tid in teams}    # full-period starters who never acted/subbed

        def place(tid, pid):
            # reveal a tip-off starter the first time they act / are subbed out (cap the floor at 5)
            if pid in on[tid] or pid in subbed_in[tid]:
                return
            if len(on[tid]) < 5:
                on[tid][pid] = (p_start, start_clk)
            else:
                problems.append((period, tid, "starter overflow"))

        for e in pev:
            tid, pid, at = e["team_id"], e["person_id"], e["action_type"]
            if not tid:
                continue
            if at == "Substitution":
                m = SUB_RE.match(e["description"] or "")
                in_pid = resolve(tid, m.group(1).strip(), frozenset(on[tid])) if m else None
                t_el, clk = elapsed(period, e["clock"]), e["clock"]
                place(tid, pid)                      # OUT player must have been on the floor
                if pid in on[tid]:
                    in_el, in_clk = on[tid].pop(pid)
                    stints.append(dict(team_id=tid, person_id=pid, period=period,
                                       in_elapsed_sec=in_el, out_elapsed_sec=t_el,
                                       in_clock=in_clk, out_clock=clk))
                else:
                    problems.append((period, tid, f"sub-out of untracked {pid}"))
                if in_pid:
                    on[tid][in_pid] = (t_el, clk)
                    subbed_in[tid].add(in_pid)
                elif m:
                    problems.append((period, tid, f"unresolved IN '{m.group(1).strip()}'"))
            elif pid:
                place(tid, pid)

        # quiet starters: on the floor the whole period but never acted/subbed -> invisible above.
        # Fill from the prior period's closing lineup (players who didn't appear at all this period).
        for tid in teams:
            seen = set(on[tid]) | subbed_in[tid] | {s["person_id"] for s in stints
                       if s["team_id"] == tid and s["period"] == period}
            for pid in prev_on[tid]:
                if len(on[tid]) + len(quiet[tid]) >= 5:
                    break
                if pid not in seen and pid not in quiet[tid]:
                    stints.append(dict(team_id=tid, person_id=pid, period=period,
                                       in_elapsed_sec=p_start, out_elapsed_sec=p_end,
                                       in_clock=start_clk, out_clock="PT00M00.00S"))
                    quiet[tid].add(pid)

        # close stints still open at period end; carry the closing lineup forward
        for tid in teams:
            for pid, (in_el, in_clk) in on[tid].items():
                stints.append(dict(team_id=tid, person_id=pid, period=period,
                                   in_elapsed_sec=in_el, out_elapsed_sec=p_end,
                                   in_clock=in_clk, out_clock="PT00M00.00S"))
            if len(on[tid]) + len(quiet[tid]) != 5:
                problems.append((period, tid, f"{len(on[tid]) + len(quiet[tid])} on floor"))
        prev_on = {tid: set(on[tid]) | quiet[tid] for tid in teams}

    for st in stints:
        st["game_id"] = meta.get("game_id")
        st["season"] = meta.get("season")
        st["season_type"] = meta.get("season_type")
    return stints, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", required=True)
    ap.add_argument("--league", default="nba", choices=["nba", "wnba"])
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--max-games", type=int, default=0)
    args = ap.parse_args()
    if args.league == "wnba":           # WNBA: separate Postgres schema + 10-min quarters
        s.SCHEMA = "wnba"
        global REG_SEC
        REG_SEC = 600
    c = s.client()

    games = sorted({r["scope"] for r in
                    s._select_all("ingestion_log", "scope",
                                  lambda q: q.eq("endpoint", "PlayByPlayV3")
                                  .eq("season", args.season).eq("status", "ok"),
                                  order="scope")})
    if args.max_games:
        games = games[:args.max_games]
    print(f"{len(games)} games for {args.season}")

    clean = flagged = 0
    prob_counts = defaultdict(int)
    for i, gid in enumerate(games, 1):
        ev = fetch_events(c, gid)
        if not ev:
            continue
        resolve = build_resolver(c, gid, ev)
        stints, problems = reconstruct(ev, resolve)
        for st in stints:
            st["game_id"] = gid
        # minutes sanity: total on-floor seconds / team vs expected 5 * game_seconds
        secs = defaultdict(float)
        for st in stints:
            secs[st["team_id"]] += (st["out_elapsed_sec"] - st["in_elapsed_sec"])
        nper = max((e["period"] for e in ev if e["period"]), default=4)
        expected = sum(period_len(p) for p in range(1, nper + 1)) * 5
        min_ok = all(abs(v - expected) < 1 for v in secs.values())
        if problems or not min_ok:
            flagged += 1
            for _, _, why in problems:
                prob_counts[re.sub(r"\d+", "N", why)] += 1
            if flagged <= 8:
                print(f"  FLAG {gid}: {len(problems)} problems, min_ok={min_ok} "
                      f"secs={ {k: round(v) for k, v in secs.items()} } exp={expected}")
        else:
            clean += 1
        if args.write:
            # delete-then-insert so re-runs with an improved algorithm don't leave orphan stints
            # (a changed in_elapsed_sec would otherwise create a duplicate rather than replace).
            _t(c, "pbp_lineup_stint").delete().eq("game_id", gid).execute()
            upsert("pbp_lineup_stint", stints,
                   pk=["game_id", "person_id", "period", "in_elapsed_sec"])
            # Per-game consistency flag: 'ok' = exactly-5/team all game + minutes balance.
            # Flagged games are still written (mostly correct) but marked so downstream can filter.
            ok = not problems and min_ok
            log("PBPLineup", season=ev[0].get("season"), season_type=ev[0].get("season_type"),
                scope=gid, status="ok" if ok else "error",
                error_msg=None if ok else f"{len(problems)} problems; min_ok={min_ok}")
        if i % 100 == 0:
            print(f"  ...{i}/{len(games)}")

    print(f"\n=== {clean} clean / {flagged} flagged of {clean + flagged} ===")
    if prob_counts:
        print("problem types:", dict(sorted(prob_counts.items(), key=lambda x: -x[1])))


if __name__ == "__main__":
    main()
