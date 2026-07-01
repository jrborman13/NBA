"""
Team-fit v1 (Path B shared style fingerprint) — production module for the Streamlit page.

Describes a player and a team in ONE 28-dim style space (style_fingerprint table) and scores fit:
  style_match = cosine of the standardized fingerprints  (does the player play like the team)
  need_fill   = cosine(player percentile profile, team DEFICIT)  (player high where team is low)
  blend       = w * z(need_fill) + (1-w) * z(style_match)   (default w near 1: need_fill carries the lift)

Backtest status (frozen Goal-1 spec, Δ on/off-net, need_fill w=1, controlled partial;
RS-only fingerprints after the season_type-collision fix):
  r = +0.087 (n=325) — BEATS both baselines (good-player×good-team, style-similarity); NOT yet
  statistically significant (p≈0.12). 80% power needs n≈1031, unreachable given the 2013-14 Synergy
  floor. So: validated to beat baseline, directional — not statistically decisive. Frame honestly.

Mirrors analysis/team_fit_pathB.py (the research/backtest reference); kept aligned.
"""
from __future__ import annotations
import numpy as np
from scipy.stats import rankdata

HONEST_NOTE = ("Validated to beat the naive baselines (good-player×good-team and style-similarity) "
               "on a 412-move backtest; **directional, not yet statistically decisive** (p≈0.12). "
               "Use as a stylistic prior, not a verdict.")

DIMS = [
    "off_Cut", "off_Handoff", "off_Isolation", "off_Misc", "off_OffRebound", "off_OffScreen",
    "off_Postup", "off_PRBallHandler", "off_PRRollman", "off_Spotup", "off_Transition",
    "def_Handoff", "def_Isolation", "def_OffScreen", "def_Postup", "def_PRBallHandler",
    "def_PRRollman", "def_Spotup",
    "z_ra", "z_paint", "z_mid", "z_corner3", "z_atb3",
    "off_trans_rate", "off_sc_rate", "off_bonus_rate", "def_trans_rate", "def_sc_rate",
]
DIM_LABELS = {
    "off_Cut": "cutting", "off_Handoff": "handoffs", "off_Isolation": "isolation",
    "off_Misc": "misc offense", "off_OffRebound": "putbacks", "off_OffScreen": "off-screen",
    "off_Postup": "post-ups", "off_PRBallHandler": "PnR ball-handler", "off_PRRollman": "PnR roll",
    "off_Spotup": "spot-up", "off_Transition": "transition O",
    "def_Handoff": "D: handoffs", "def_Isolation": "D: isolation", "def_OffScreen": "D: off-screen",
    "def_Postup": "D: post-ups", "def_PRBallHandler": "D: PnR ball-handler",
    "def_PRRollman": "D: PnR roll", "def_Spotup": "D: spot-up",
    "z_ra": "shots at rim", "z_paint": "paint shots", "z_mid": "mid-range",
    "z_corner3": "corner 3s", "z_atb3": "above-break 3s",
    "off_trans_rate": "plays in transition", "off_sc_rate": "second-chance O",
    "off_bonus_rate": "bonus/FT pressure", "def_trans_rate": "transition D", "def_sc_rate": "second-chance D",
}
MIN_MPG = 15.0


class SeasonFit:
    """One season's standardized fingerprints + percentiles + fit scoring + embedding."""

    def __init__(self, client, season):
        self.season = season
        rows = self._page(client, "style_fingerprint", "entity_type,entity_id,dim,value",
                          [("season", season), ("season_type", "Regular Season")])
        fp = {}
        for r in rows:
            if r["value"] is not None:
                fp.setdefault((r["entity_type"], r["entity_id"]), {})[r["dim"]] = float(r["value"])
        qual = {r["player_id"] for r in self._page(
            client, "v_player_usage_efficiency", "player_id,min",
            [("season", season), ("season_type", "Regular Season")])
            if r["min"] is not None and float(r["min"]) >= MIN_MPG}
        self.player_name = {r["player_id"]: r["player_name"] for r in self._page(
            client, "v_player_usage_efficiency", "player_id,player_name", [("season", season)])}
        self.team_name = {r["team_id"]: r["team_name"] for r in self._page(
            client, "team_needs", "team_id,team_name", [("season", season)])}

        self.players = {eid: self._fill(d) for (et, eid), d in fp.items() if et == "P" and eid in qual}
        self.teams = {eid: self._fill(d) for (et, eid), d in fp.items() if et == "T"}
        if not self.players or not self.teams:
            raise RuntimeError(f"team_fit: empty pool for {season} (materialized/backfilled?)")

        M = np.array(list(self.players.values()) + list(self.teams.values()), float)
        self.mu, self.sd = M.mean(0), M.std(0)
        self.sd[self.sd == 0] = 1.0
        self.p_pct = self._pctiles(self.players)
        self.t_pct = self._pctiles(self.teams)

    @staticmethod
    def _page(client, table, select, filters):
        out, start = [], 0
        while True:
            q = client.table(table).select(select)
            for c, v in filters:
                q = q.eq(c, v)
            data = q.range(start, start + 999).execute().data
            if not data:
                break
            out.extend(data)
            if len(data) < 1000:
                break
            start += 1000
        return out

    @staticmethod
    def _fill(d):
        return np.array([d.get(dim, 0.0) for dim in DIMS], float)  # missing dim = real 0

    def _pctiles(self, pool):
        ids = list(pool)
        M = np.array([pool[i] for i in ids], float)
        out = {i: {} for i in ids}
        for j, dim in enumerate(DIMS):
            pr = rankdata(M[:, j]) / len(ids) * 100.0
            for i, p in zip(ids, pr):
                out[i][dim] = float(p)
        return out

    def _vec(self, v):
        return (v - self.mu) / self.sd

    @staticmethod
    def _cos(a, b):
        da, db = np.linalg.norm(a), np.linalg.norm(b)
        return float(a @ b / (da * db)) if da and db else 0.0

    def _components(self, player_id, team_id):
        pv, tv = self.players.get(player_id), self.teams.get(team_id)
        if pv is None or tv is None:
            return None
        style = self._cos(self._vec(pv), self._vec(tv))
        pp = np.array([self.p_pct[player_id][d] for d in DIMS])
        tp = np.array([self.t_pct[team_id][d] for d in DIMS])
        need = self._cos(pp - pp.mean(), (100 - tp) - (100 - tp).mean())
        return style, need

    def rank_teams(self, player_id, w=0.9):
        """Rank all teams for a player. Returns list of dicts sorted by blended fit (z-scored across teams)."""
        rows = []
        for tid in self.teams:
            comp = self._components(player_id, tid)
            if comp:
                rows.append({"team_id": tid, "team": self.team_name.get(tid, tid),
                             "style_match": comp[0], "need_fill": comp[1]})
        if not rows:
            return []
        sm = np.array([r["style_match"] for r in rows])
        nf = np.array([r["need_fill"] for r in rows])
        zsm = (sm - sm.mean()) / (sm.std() or 1)
        znf = (nf - nf.mean()) / (nf.std() or 1)
        for i, r in enumerate(rows):
            r["blend"] = float(w * znf[i] + (1 - w) * zsm[i])
        return sorted(rows, key=lambda r: r["blend"], reverse=True)

    def explain(self, player_id, team_id, top=4):
        """Top dims the player supplies that the team lacks: (label, player_pctile, team_pctile)."""
        if player_id not in self.p_pct or team_id not in self.t_pct:
            return []
        pp, tp = self.p_pct[player_id], self.t_pct[team_id]
        scored = sorted(((pp[d] * (100 - tp[d]), d) for d in DIMS), reverse=True)
        return [(DIM_LABELS.get(d, d), round(pp[d]), round(tp[d])) for _, d in scored[:top]]

    def embedding(self):
        """2D PCA coords for players (P) + teams (T). Returns dict {(etype,id): (x,y)}."""
        from sklearn.decomposition import PCA
        ids = [("P", i) for i in self.players] + [("T", i) for i in self.teams]
        X = np.array([self._vec(self.players[i] if et == "P" else self.teams[i]) for et, i in ids])
        XY = PCA(n_components=2).fit_transform(X)
        return {ids[k]: (float(XY[k, 0]), float(XY[k, 1])) for k in range(len(ids))}
