# CBA Compliance Engine — Data Foundation

The data layer the transaction-legality checker reasons over. The rule
knowledge base lives in `../kb/`; this folder is the **state + numbers** the
rules resolve against.

## What's here

```
engine/
├── db/
│   ├── 001_schema.sql               # Supabase/Postgres tables
│   └── 002_seed_league_constants.sql# verified cap/tax/apron/MLE figures (2023-24 → 2025-26)
├── calculator/
│   └── team_salary.py               # Team Salary + cap/tax/apron tiers (implements rules_salary_cap)
└── ingest/
    └── spotrac_loader.py            # Spotrac export → contract table mapping
```

## Why it's built this way

Accuracy comes from making the deterministic parts deterministic. The CBA is
arithmetic and hard thresholds; those live in code (`team_salary.py`) and in
data (`league_constants`), not in model reasoning. The rule JSON references a
threshold **by name** ("Non-Taxpayer Mid-Level Salary Exception"); the engine
resolves the dollar value from `league_constants` for the season. That
indirection is what keeps the engine correct every July when the cap moves.

## Build order

1. **Apply schema + seed** (done): run `001_schema.sql` then
   `002_seed_league_constants.sql` against Supabase.
2. **Load contracts** (next): obtain a Spotrac export, adjust
   `SPOTRAC_COLUMN_MAP` to your headers, run `map_spotrac_rows` + upsert.
   Backfill cap holds and roster counts per team-season.
3. **Compute + validate**: run `compute_team_salary` per team-season and
   write `team_salary_state`. **Validation target:** the computed team salary
   and apron tier must match the publicly known values for every team in a
   season you have full data for. That's the first regression test and a hard,
   objective accuracy check.
4. **Build the rule engine on top**: deterministic predicates for trades /
   aprons / max-salary, using these constants and team states as inputs.

## Known follow-ups

- Seed `min_salary_scale` and `rookie_scale` (Exhibit B/C baselines escalated
  per cap year) — needed for minimum signings, rookie deals, and the
  Incomplete Roster Charge's exact figure.
- Confirm the 2024-25 bi-annual exact published value (currently computed as
  3.32% of cap).
- Wire `MIN_ROSTER_FOR_CHARGE` and non-counting contract types to the exact
  thresholds in `rules_salary_cap.json` rather than the placeholder constants.
- Add pre-2023-24 seasons (aprons null) to validate the core cap/tax math.

## Data-source note

Spotrac's terms restrict scraping and its pages are JS-rendered. Supply the
data through access you have (export / authenticated pull); the loader maps
whatever you provide. Nothing here fetches spotrac.com directly.
