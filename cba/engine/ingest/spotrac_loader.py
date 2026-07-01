"""
Spotrac -> contract table loader.

Spotrac is JavaScript-rendered and its terms restrict scraping, so this
module does NOT fetch from spotrac.com. It maps an already-obtained Spotrac
export (CSV/DataFrame you pull through access you have) into rows for the
`contract` table in cba/engine/db/001_schema.sql.

Adjust SPOTRAC_COLUMN_MAP to match the exact headers in your export, then:
    rows = map_spotrac_rows(df, season="2025-26")
    upsert_contracts(rows)   # via your supabase client
"""
from __future__ import annotations

# Expected Spotrac export columns -> our schema fields.
# LEFT = header in your Spotrac CSV; RIGHT = contract table column.
# Confirm/adjust against your actual export before first load.
SPOTRAC_COLUMN_MAP = {
    "Player":            "player_name",
    "Team":              "team_abbr",
    "Cap Hit":           "cap_figure",       # what counts toward Team Salary
    "Base Salary":       "base_salary",
    "Likely Incentives": "likely_bonuses",
    "Unlikely Incentives": "unlikely_bonuses",
    "Signing Bonus":     "signing_bonus_proration",
    "Type":              "contract_type",    # normalized below
    "Guaranteed":        "guaranteed_amount",
    "Option":            "option_type",      # normalized below
    "Trade Kicker":      "trade_bonus_pct",
    "No-Trade":          "no_trade",
}

# Spotrac type/option wording -> our controlled vocabulary.
TYPE_NORMALIZE = {
    "rookie": "rookie_scale", "rookie scale": "rookie_scale",
    "two-way": "two_way", "2-way": "two_way",
    "10-day": "10_day", "minimum": "minimum",
    "veteran": "standard", "standard": "standard", "": "standard",
}
OPTION_NORMALIZE = {
    "team": "team", "to": "team",
    "player": "player", "po": "player",
    "eto": "eto", "early termination": "eto",
    "": "none", None: "none",
}


def _money(v) -> int | None:
    if v is None or v == "":
        return None
    return int(round(float(str(v).replace("$", "").replace(",", ""))))


def map_spotrac_rows(df, season: str) -> list[dict]:
    """Map a Spotrac export (pandas DataFrame) to contract dicts.

    Currency strings like '$1,234,567' are coerced to int dollars. Unmapped
    rows raise rather than silently drop (fail loud — see project rules).
    """
    rows = []
    for _, r in df.iterrows():
        out = {"season": season, "source": "spotrac"}
        for col, field in SPOTRAC_COLUMN_MAP.items():
            if col not in df.columns:
                continue
            val = r[col]
            if field in ("cap_figure", "base_salary", "likely_bonuses",
                         "unlikely_bonuses", "signing_bonus_proration",
                         "guaranteed_amount"):
                out[field] = _money(val)
            elif field == "contract_type":
                out[field] = TYPE_NORMALIZE.get(str(val).strip().lower(), "standard")
            elif field == "option_type":
                out[field] = OPTION_NORMALIZE.get(str(val).strip().lower(), "none")
            elif field == "no_trade":
                out[field] = str(val).strip().lower() in ("y", "yes", "true", "1")
            else:
                out[field] = None if val == "" else val
        if not out.get("player_name"):
            raise ValueError(f"Spotrac row missing player name: {r.to_dict()}")
        if out.get("cap_figure") is None:
            raise ValueError(f"Spotrac row missing cap figure for {out['player_name']}")
        rows.append(out)
    return rows


def upsert_contracts(rows: list[dict], supabase_client) -> int:
    """Upsert mapped rows into the contract table. Returns count."""
    if not rows:
        return 0
    supabase_client.table("contract").upsert(rows).execute()
    return len(rows)
