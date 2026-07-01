-- =====================================================================
-- NBA CBA Compliance Engine — Supabase / Postgres schema
-- Data foundation for the transaction-legality checker.
-- All money stored as BIGINT dollars (exact; no float rounding).
-- Season strings use the project convention: '2025-26'.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. league_constants — the year-specific numbers the CBA rules resolve
--    against. Rules in cba/kb/rules_*.json reference thresholds
--    SYMBOLICALLY (e.g. "Non-Taxpayer Mid-Level Salary Exception");
--    the engine looks up the dollar value here for the relevant season.
--    This indirection is what keeps the engine correct across cap years.
-- ---------------------------------------------------------------------
create table if not exists league_constants (
    season            text primary key,            -- '2025-26'
    salary_cap        bigint not null,
    tax_level         bigint not null,
    first_apron       bigint,                       -- null pre-2023-24 (no aprons)
    second_apron      bigint,                       -- null pre-2023-24
    min_team_salary   bigint,                       -- 90% of cap
    nontax_mle        bigint,                       -- Non-Taxpayer Mid-Level Salary Exception (yr-1)
    tax_mle           bigint,                       -- Taxpayer Mid-Level Salary Exception (yr-1)
    room_mle          bigint,                       -- Mid-Level Salary Exception for Room Teams (yr-1)
    biannual          bigint,                       -- Bi-annual Exception (yr-1)
    est_avg_salary    bigint,                       -- used by some exception/QO calcs
    apron_era         boolean default false,        -- true for 2023-24 onward
    is_estimated      boolean default false,        -- true if any value is projected/unconfirmed
    source            text,
    source_url        text,
    effective_date    date,
    notes             text,
    updated_at        timestamptz default now()
);

-- ---------------------------------------------------------------------
-- 2. min_salary_scale — Minimum Annual Salary by Years of Service,
--    per season (Exhibit C baseline, escalated each cap year).
-- ---------------------------------------------------------------------
create table if not exists min_salary_scale (
    season            text references league_constants(season),
    years_of_service  int  not null,                -- 0,1,2,...,10+ (use 10 for "10 or more")
    amount            bigint not null,
    primary key (season, years_of_service)
);

-- ---------------------------------------------------------------------
-- 3. rookie_scale — first-round Rookie Scale Amounts by draft year,
--    pick, and contract year (Exhibit B baseline, escalated).
-- ---------------------------------------------------------------------
create table if not exists rookie_scale (
    draft_year        int  not null,                -- year the player was drafted
    pick              int  not null,                -- 1..30
    year_num          int  not null,                -- 1..4 (yrs 3-4 are team options)
    amount            bigint not null,
    is_option_year    boolean default false,
    primary key (draft_year, pick, year_num)
);

-- ---------------------------------------------------------------------
-- 4. contract — one row per player per cap year (Spotrac-fed).
--    cap_figure is the value that counts toward Team Salary
--    (base + Likely Bonuses + applicable proration). Keep the raw
--    components so the engine can recompute under rule changes.
-- ---------------------------------------------------------------------
create table if not exists contract (
    id                    bigserial primary key,
    player_id             text,
    player_name           text not null,
    team_id               int,
    team_abbr             text,
    season                text references league_constants(season),
    cap_figure            bigint not null,           -- counts toward Team Salary
    base_salary           bigint,
    likely_bonuses        bigint default 0,          -- count toward cap
    unlikely_bonuses      bigint default 0,          -- excluded from cap (track for apron/hard-cap)
    signing_bonus_proration bigint default 0,
    contract_type         text,                      -- standard|rookie_scale|two_way|10_day|
                                                     -- rest_of_season|minimum|exhibit10
    guarantee_status      text,                      -- guaranteed|partial|non_guaranteed
    guaranteed_amount     bigint,
    option_type           text default 'none',       -- none|team|player|eto
    is_option_year        boolean default false,
    trade_bonus_pct       numeric(5,4) default 0,
    no_trade              boolean default false,
    is_dead_money         boolean default false,     -- waived player still on cap
    acquired_via          text,                      -- draft|fa|trade|claim (for trade/aggregation timing)
    signed_date           date,                      -- for trade-eligibility windows
    source                text default 'spotrac',
    source_url            text,
    ingested_at           timestamptz default now()
);
create index if not exists idx_contract_team_season on contract(team_id, season);
create index if not exists idx_contract_player on contract(player_id);

-- ---------------------------------------------------------------------
-- 5. cap_hold — non-contract charges that count toward Team Salary:
--    Free Agent Amounts (cap holds), rookie holds, exception amounts
--    held, and the Incomplete Roster Charge. Drives accurate cap room.
-- ---------------------------------------------------------------------
create table if not exists cap_hold (
    id          bigserial primary key,
    team_id     int  not null,
    season      text references league_constants(season),
    hold_type   text not null,        -- free_agent|rookie_hold|exception|incomplete_roster
    player_id   text,                  -- null for exception / incomplete-roster charges
    player_name text,
    amount      bigint not null,
    rights_tier text,                  -- bird|early_bird|non_bird (for free_agent holds)
    notes       text
);
create index if not exists idx_caphold_team_season on cap_hold(team_id, season);

-- ---------------------------------------------------------------------
-- 6. team_roster_state — inputs the calculator needs that aren't a
--    single contract: roster count (for Incomplete Roster Charge) and
--    outstanding Traded Player Exceptions.
-- ---------------------------------------------------------------------
create table if not exists team_roster_state (
    team_id        int,
    season         text references league_constants(season),
    roster_count   int,                              -- players on standard contracts
    outstanding_tpes jsonb default '[]'::jsonb,      -- [{amount, expires_on, created_via}]
    primary key (team_id, season)
);

-- ---------------------------------------------------------------------
-- 7. team_salary_state — COMPUTED output of the calculator. Validation
--    target: these must match publicly known team salary / apron tier
--    for any season you have full contract data for.
-- ---------------------------------------------------------------------
create table if not exists team_salary_state (
    team_id            int,
    season             text references league_constants(season),
    team_salary        bigint not null,
    cap_room           bigint,                        -- positive = room; negative = over cap
    over_tax           boolean,
    over_first_apron   boolean,
    over_second_apron  boolean,
    hard_cap_level     text default 'none',           -- none|first_apron|second_apron
    computed_at        timestamptz default now(),
    engine_version     text,
    primary key (team_id, season)
);
