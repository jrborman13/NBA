# NBA Supabase Stat Ideas

**Source of truth:** `SUPABASE_DATA_CATALOG.md` (project `qhrgekcowkgwcaaqyqvv`).
**Process:** Each idea was proposed, vetted for analytical value, then debated against build
cost and the documented data gotchas before being kept. Every entry below is one I'm confident
we can build in Claude Code against the existing schema.

**Legend**
- **Cost:** Light (season tables / matviews, no PBP), Medium (game-logs + light PBP or single-game PBP), Heavy (season-wide `lineup_at_event` / PBP grouping → must materialize first).
- **Confidence:** how sure I am the data supports it cleanly, end to end.

---

## 1. Rolling Custom-Window Net Rating ("hot/cold form")

**What it measures.** Team OffRtg / DefRtg / NetRtg / Pace over an arbitrary recent window
(last 5/10/15 games, post-All-Star, since a trade, home-only) instead of the season-frozen
number the NBA API hands back.

**Why it matters.** The single most-asked pregame question on the show is "who's actually
good *right now*." A season-grain Net Rating buries a team that was bad in November and elite
since January. A rolling window is the honest answer to "are the Wolves trending up?"

**Self-debate.** *For:* highest-leverage, lowest-risk idea — directly improves every matchup
take. *Against:* is it just a moving average of `team_game_logs` PLUS_MINUS? Partly, but
PLUS_MINUS is raw point margin, not pace-adjusted; two teams at +5 can be very different at
different paces. *Resolution:* compute possessions per game so the window is per-100, not raw.
We can get there two ways — cheap (sum the box terms `FGA + 0.44*FTA - OREB + TOV` from
`team_game_logs.stats` per game, no PBP needed) or exact (PBP). The box-term route is plenty
accurate at game grain and avoids PBP entirely. Kept, build it cheap first.

**Data.** `team_game_logs` (`stats` jsonb: PTS, FGA, FTA, OREB, TOV, PLUS_MINUS) + `schedule`
for opponent/home-away context. Optionally `mv_team_form` for the L5/L10 PTS baseline.

**Approach.** Per team, order by `game_date DESC`, take last N, sum points for/against
(against = PTS − PLUS_MINUS), estimate possessions from box terms, express per-100.

**Cost:** Medium · **Confidence:** High.

---

## 2. "A-without-B" Staggering Splits

**What it measures.** Team net rating in three states for a star pair: both on, A-on/B-off,
B-on/A-off (and both off). The classic question — does the bench survive when the star sits,
and is the second star a real lead-ball-handler or a passenger?

**Why it matters.** This is the lineup question the official ON/OFF endpoint **cannot** answer.
`mv_player_onoff` gives "A on vs A off" league-wide, but not "A on *while B sits*." Staggering
is the difference between a coach who keeps the offense afloat all 48 and one who gets caved
in the 4–8 minute bench stretches.

**Self-debate.** *For:* genuinely unavailable elsewhere, high storytelling value. *Against:*
this is the expensive one — `lineup_at_event.on_floor` is a per-event correlated subquery,
"slow over a whole season" per the catalog. *Resolution:* the catalog itself prescribes the
fix — materialize a per-event table (`elapsed_sec`, point delta, possession flag, `on_floor`)
for the seasons we care about, then array-filter `on_floor @> ARRAY['A'] AND NOT on_floor @>
ARRAY['B']`. Build the matview once, query cheaply forever. Kept, but flagged Heavy.

**Data.** `lineup_at_event` (materialized) + `play_by_play` running score deltas.

**Cost:** Heavy (materialize first) · **Confidence:** Medium-High (mechanics are proven; cost is the only risk).

---

## 3. Custom Clutch Lineup Net Rating

**What it measures.** Net rating per 5-man unit restricted to clutch time, with **our own**
clutch definition (e.g. last 4 min, margin ≤ 6) rather than the NBA's fixed "last 5, ≤5."

**Why it matters.** Closing lineups decide playoff series and a shocking number of regular-season
games. "Which 5 does Finch actually close with, and do they win those minutes" is a recurring
segment. The pre-computed `*_clutch` tables are player/team season aggregates — they can't tell
you *which lineup* is on the floor in crunch time.

**Self-debate.** *For:* combines two things the API can't — custom clutch threshold *and*
lineup grain. *Against:* clutch samples are tiny; a 5-man unit might have 30 clutch possessions
all season → noisy. *Resolution:* real concern. Mitigate by (a) always showing possession
count next to the rating, (b) defaulting to 2–3 man combos in clutch rather than full 5-man
(bigger samples), (c) pooling multiple seasons via the matview. Kept with a hard "show N"
guardrail so we never put a 12-possession number on air as if it's stable.

**Data.** `play_by_play` (period ≥ 4, `clock` threshold, running-score margin) + the §2
materialized lineup table.

**Cost:** Heavy · **Confidence:** Medium (sample-size honesty required).

---

## 4. Shot-Selection vs Shot-Making (expected eFG% gap)

**What it measures.** For a team or player, expected eFG% = their shot diet (frequency by
`shot_zone`) weighted by **league-average** eFG% in each zone, vs their actual eFG%. The gap
separates *selection* (do they take good shots?) from *making* (do they hit shots above
expectation?).

**Why it matters.** A team can be a bad-shooting team two completely different ways: bad shot
diet (lots of long mid-range) or good diet but cold. The fix is different, and the regression
story is different (cold-but-good-diet teams bounce back; bad-diet teams don't). This is a
sharp, defensible on-air narrative.

**Self-debate.** *For:* turns the raw `shot_event` zones into an insight, not just a chart.
*Against:* "expected eFG%" using only zone ignores defender distance and shot clock — it's a
proxy, not true shot quality. *Resolution:* be honest in labeling ("zone-based expected eFG%,"
not "shot quality"). We don't have defender data on the PBP side, so zone is the best available
and is still highly informative. Kept, with careful naming so we don't overclaim.

**Data.** `shot_event` (`shot_zone`, `shot_value`, `shot_result`). League zone baselines
computed once per season from the same view.

**Cost:** Light–Medium · **Confidence:** High.

---

## 5. Self-Creation Index (assisted vs unassisted rate)

**What it measures.** Share of a player's made FGs that were **unassisted**
(`assist_person_id IS NULL` on `Made Shot`), split by zone and shot value — i.e. how much of
their scoring they generate themselves vs. off a teammate's pass.

**Why it matters.** Separates engine-creators from finishers. Two 20-PPG scorers can have
totally different team value: one needs the ball and creates, the other needs a creator to feed
him. Directly informs "can this guy carry a bench unit" and trade/fit takes.

**Self-debate.** *For:* trivially available from `shot_event`, high explanatory power.
*Against:* assisted-rate is influenced by teammates (a great passer inflates everyone's assisted
rate) — it's not purely individual. *Resolution:* that's a feature, not a bug, as long as we
frame it as "how this player scores *in this context*," not a context-free skill rating. Pair it
with §6 to see who's feeding him. Kept.

**Data.** `shot_event` (`shooter_id`, `assist_person_id`, `shot_zone`, `shot_value`).

**Cost:** Light · **Confidence:** High.

---

## 6. Passing-Network Connection Strength ("who creates for whom")

**What it measures.** Directed passer→shooter "chemistry": assists and points generated on the
A→B connection, plus FG% the receiver shoots off A's passes vs. their baseline. Surfaces the
strongest 2-man offensive connections and each player's network centrality.

**Why it matters.** Lineup construction and injury-impact analysis. If A→B is a team's best
pipe and A sits, you can predict B's drop before the game. Great visual segment (assist network)
and a real analytical tool for "what breaks when X is out."

**Self-debate.** *For:* `player_passing` is purpose-built for this and is Light cost. *Against:*
is it more than a pretty graph? *Resolution:* yes — the receiver-shooting-off-passes angle
(`FG_PCT` in the jsonb vs the receiver's own baseline) makes it analytical, not decorative.
That delta is the actual chemistry signal. Kept.

**Data.** `player_passing` (`player_id`, `pass_teammate_player_id`, `pass_direction`, `stats`:
PASS, AST, FREQUENCY, FG_PCT/FG2_PCT/FG3_PCT).

**Cost:** Light · **Confidence:** High.

---

## 7. Bench-Unit Net Rating & Lineup Continuity

**What it measures.** Net rating of all-bench (or ≤1 starter) lineups, and a continuity metric —
how often a team reuses the same 5 vs constantly shuffling.

**Why it matters.** Bench performance and rotation stability are season-long storylines and a
common reason good starting fives still lose games. "The starters are +8, the bench is −11" is
a a recurring, true, and useful framing.

**Self-debate.** *For:* directly actionable, ties to a clear narrative. *Against:* "starter"
isn't a labeled field — we have to define it (e.g. top-5 by minutes, or who's on floor at tip).
Also Heavy (same `lineup_at_event` materialization as §2). *Resolution:* define starter = the 5
on `on_floor` at the game's first event (clean, per-game, no ambiguity). Reuses the §2 matview,
so marginal cost is low once that exists. Kept; bundle the build with §2/§3.

**Data.** §2 materialized lineup table + first-event starter detection from `play_by_play`.

**Cost:** Heavy (shares §2 build) · **Confidence:** Medium-High.

---

## 8. Scoring-Run & Game-Volatility Profile

**What it measures.** Per game and aggregated: largest scoring run by each team, number of lead
changes, time spent leading, and a volatility score (how swingy the margin is). Aggregated to a
team's season "identity" — wire-to-wire vs comeback vs collapse-prone.

**Why it matters.** Postgame, the run that decided the game *is* the story, and pulling it
automatically within 10 minutes of the buzzer is exactly the show's use case. Aggregated, it
flags teams whose record over/undersells them (a team that wins close and loses big is fragile).

**Self-debate.** *For:* pure `play_by_play` score work, no lineup cost; perfect postgame fit.
*Against:* the catalog warns scores are sparse (~26% of events populated). *Resolution:* the
catalog also gives the exact fix — reconstruct running score with
`max(score_*) OVER (ORDER BY event_idx)` then `lag()` for deltas. Standard, single-game scope =
fast. Kept; this is a postgame staple.

**Data.** `play_by_play` (`score_home`, `score_away`, `event_idx`, `period`, `clock`).

**Cost:** Medium (single-game fast; season aggregation moderate) · **Confidence:** High.

---

## 9. Usage–Efficiency Quadrant (custom window)

**What it measures.** Player usage rate vs true shooting over a chosen window, plotted as a
quadrant: high-usage/high-efficiency (stars), high-usage/low-efficiency (volume scorers / empty
calories), low-usage/high-efficiency (efficient role players), low/low.

**Why it matters.** One chart that frames a whole roster's offensive roles and flags the
"chucker" vs the "efficient star." Also a fantasy/DFS lens — high-usage guys with a soft matchup
are the projection movers.

**Self-debate.** *For:* `USG_PCT` and `TS_PCT` are pre-computed in `player_season_stats`
(Advanced) — Light at season grain. *Against:* then it's trivial and not novel. *Resolution:*
the novelty is the *custom window* — derive usage over last-N from box terms
(`(FGA + 0.44*FTA + TOV)` player vs on-court team total) so we can show "usage since the injury"
not just season. Season version is the free Light starter; windowed version is the upgrade.
Kept, phased.

**Data.** Season: `player_season_stats` (Advanced). Windowed: `player_game_logs` + on-court team
totals via `lineup_at_event` (or team game logs as an approximation).

**Cost:** Light (season) → Medium (windowed) · **Confidence:** High (season), Medium (windowed accuracy).

---

## 10. Rest & Schedule-Spot Impact (B2B / days-rest splits)

**What it measures.** Team and player performance split by rest situation — 0 days (back-to-back),
1 day, 2+, plus home/away — using net rating and key box stats. Derived purely from
`schedule` game dates.

**Why it matters.** Schedule spots are one of the most reliable, least-priced edges in both
analysis and DFS. "Wolves on the second night of a road B2B" is a real, repeatable pattern, and
B2B fatigue is a legitimate pregame angle every single night.

**Self-debate.** *For:* cheap (game logs + date arithmetic), evergreen, betting-relevant.
*Against:* rest samples per team per season are small (~12–15 B2Bs) → noisy single-season.
*Resolution:* pool multiple seasons (coverage goes back to 2005-06) for the team-level baseline,
and present current-season as a smaller live sample on top. The historical pooled split is
stable. Kept.

**Data.** `team_game_logs` / `player_game_logs` + `schedule` (compute days between games per team).

**Cost:** Medium · **Confidence:** High.

---

## 11. Defensive Matchup-Exploit Finder (Synergy play-type mismatch)

**What it measures.** For an upcoming matchup, cross each team's **offensive** play-type
strengths (`synergy_playtypes` offensive PPP/percentile/frequency) against the opponent's
**defensive** weaknesses (defensive grouping PPP-allowed/percentile). Surfaces the top
exploitable mismatches — "Team X is elite at PnR roll-man; Opponent is bottom-5 defending it."

**Why it matters.** This is a *prep* tool, not a postmortem — it tells you what to watch for
before tip and what each team will try to attack. Exactly the kind of pre-show angle that sounds
sharp and is grounded in real numbers, not vibes.

**Self-debate.** *For:* both offensive and defensive groupings already exist in
`synergy_playtypes` (`type_grouping`), so it's a join, not a derivation — Light. *Against:*
Synergy frequency is team-wide; it doesn't guarantee the matchup actually plays out (a coach can
scheme away from a weakness). *Resolution:* true, so frame as "available edges," ranked by
frequency × efficiency-gap so we don't over-index on a play type that rarely happens. Kept.

**Data.** `synergy_playtypes` (`entity_type='team'`, both `type_grouping` values, `stats`: PPP,
POSS_PCT, PERCENTILE).

**Cost:** Light · **Confidence:** High.

---

## 12. Player "Shot-Diet Gravity" (on/off team shot quality)

**What it measures.** How a team's **expected eFG%** (from §4's zone model) changes when a
given player is on vs off the floor — a proxy for offensive gravity / spacing impact that
shows up in *teammates'* shot quality, not the player's own box score.

**Why it matters.** Captures value that counting stats miss — the elite spacer or playmaker who
makes everyone *else's* shots better. This is the analytical case for players whose impact
"doesn't show in the box score," made concrete.

**Self-debate.** *For:* genuinely differentiated, combines two assets (`shot_event` +
`lineup_at_event`) into something neither gives alone. *Against:* this is the most complex idea
here — needs the §2 lineup materialization *and* the §4 zone model joined at event grain, and
the causal claim ("gravity") is a proxy stacked on a proxy. *Resolution:* worth it but sequence
it last — only attempt after §2 and §4 are built and trusted. Label it explicitly as a proxy.
Kept as a stretch/flagship build, not an early one.

**Data.** §2 materialized lineup table joined to `shot_event` + §4 league zone baselines.

**Cost:** Heavy · **Confidence:** Medium (high value, highest complexity — build last).

---

## 13. Second-Chance Possession Value (inferred OREB)

**What it measures.** Offensive-rebound rate and the *points generated off second chances* per
team — possessions extended by an OREB and what they're worth (PPP on putback/kickout
possessions vs the team's overall PPP).

**Why it matters.** Offensive rebounding is a swing skill that wins playoff games and is
under-covered. "They got 18 second-chance points" is a clean postgame stat, and the rate is a
real team-identity marker.

**Self-debate.** *For:* fills a gap — the box has OREB counts but not the *value* of the
possessions they create. *Against:* the catalog flags that rebound `sub_type` is ~95% 'Unknown',
so OREB isn't directly labeled. *Resolution:* the catalog gives the inference rule — a rebound
is offensive when its `team_id` matches the immediately preceding missed-shot team. That sequence
logic is reliable in PBP. We then tag the points scored before the next possession change. More
involved than counting, but mechanically sound. Kept, with the OREB-inference helper as a shared
building block (it's reusable across ideas).

**Data.** `play_by_play` (sequence of `Missed Shot` → `Rebound` → ensuing scoring), `team_id`.

**Cost:** Medium · **Confidence:** Medium-High (inference is sound but needs validation against known OREB totals).

---

## Build Sequencing (recommendation)

**Phase 1 — Light, immediate wins (no PBP):** #6 passing network, #11 matchup-exploit finder,
#5 self-creation index, #4 shot selection-vs-making, #9 usage-efficiency (season version).

**Phase 2 — Medium (game logs + single-game PBP):** #1 rolling net rating, #8 scoring runs,
#10 rest splits, #13 second-chance value.

**Phase 3 — Heavy (build the `lineup_at_event` materialization once, then reuse):** #2 staggering
splits, #7 bench units, #3 clutch lineups, then #12 shot-diet gravity as the flagship.

**Shared building blocks worth building first:** (a) the per-event materialized lineup table
(unlocks #2, #3, #7, #12), (b) the OREB-inference helper (#13 and any possession work),
(c) league-average zone eFG% baselines (#4 and #12).

**Verification step for any of these before it goes on air:** validate derived numbers against
the pre-computed season tables where overlap exists — e.g. season-grain rolling net rating (#1)
should reconcile with `team_season_stats` Advanced `NET_RATING`; derived usage (#9) with
`player_season_stats` `USG_PCT`; inferred OREB totals (#13) with `player_game_logs` `OREB`. If
the derivation doesn't tie out to the official number at season grain, the custom-window version
isn't trustworthy either.
