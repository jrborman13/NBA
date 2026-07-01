-- Run this in the Supabase SQL Editor (Dashboard → SQL Editor → New Query)
-- Creates the parlay_log table used by parlay_tracker.py

create table if not exists parlay_log (
    id                uuid primary key default gen_random_uuid(),
    game_date         date not null,
    logged_at         timestamptz not null default now(),
    legs              jsonb not null,          -- array of leg objects
    status            text not null default 'pending'
                          check (status in ('pending', 'won', 'lost')),
    units_risked      numeric(6,2) not null default 1.0,
    payout_multiplier numeric(8,4),            -- profit multiplier (e.g. 5.95)
    legs_won          int,                     -- null until verified
    legs_total        int not null,
    units_returned    numeric(8,4),            -- null until verified
    verified_at       timestamptz
);

-- Index for common queries
create index if not exists parlay_log_game_date_idx on parlay_log (game_date);
create index if not exists parlay_log_status_idx    on parlay_log (status);
create index if not exists parlay_log_logged_at_idx on parlay_log (logged_at desc);

-- Optional: enable Row Level Security (open read/write for anon key)
-- alter table parlay_log enable row level security;
-- create policy "allow all" on parlay_log for all using (true) with check (true);
