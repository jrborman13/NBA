# Passing Page - Available Endpoints & Stats Reference

## API Endpoint Used
- **Endpoint**: `nba_api.stats.endpoints.PlayerDashPtPass`
- **Parameters**:
  - `season`: '2025-26' (or other season)
  - `season_type_all_star`: 'Regular Season' (or 'Playoffs', 'Pre Season', 'All Star')
  - `per_mode_simple`: 'PerGame' (or 'Totals', 'Per36', 'Per100Possessions', etc.)
  - `player_id`: Player ID (string)
  - `team_id`: Team ID (string)

## Currently Displayed Stats

### Key Metrics (Top 4 Metrics)
1. **FREQUENCY** - Passes Per Game (frequency of passes to receiver)
2. **FG_PCT** - Field Goal % When Receiving
3. **AST** - Assists Per Game
4. **FGM / FGA** - Field Goals Made / Field Goals Attempted

### Detailed Statistics Table (Currently Shown)
- **PASS_TO** - Receiver name
- **FREQUENCY** - Pass frequency
- **AST** - Assists
- **FGM** - Field Goals Made
- **FGA** - Field Goals Attempted
- **FG_PCT** - Field Goal Percentage
- **FG2M** - 2-Point Field Goals Made
- **FG2A** - 2-Point Field Goals Attempted
- **FG2_PCT** - 2-Point Field Goal Percentage
- **FG3M** - 3-Point Field Goals Made
- **FG3A** - 3-Point Field Goals Attempted
- **FG3_PCT** - 3-Point Field Goal Percentage

## All Available Stats from API (Not Currently Displayed)

### Player/Team Identification
- **PLAYER_ID** - Passer's player ID
- **PLAYER_NAME_LAST_FIRST** - Passer's name (Last, First format)
- **TEAM_NAME** - Team name
- **TEAM_ID** - Team ID
- **TEAM_ABBREVIATION** - Team abbreviation (e.g., "MIN")
- **PASS_TEAMMATE_PLAYER_ID** - Receiver's player ID
- **PASS_TO** - Receiver's name

### Game Context
- **G** - Games played
- **PASS_TYPE** - Type of pass (e.g., "made")

### Passing Metrics
- **FREQUENCY** - Frequency of passes to this teammate (currently displayed)

### Scoring Stats
- **AST** - Assists (currently displayed)
- **FGM** - Field Goals Made (currently displayed)
- **FGA** - Field Goals Attempted (currently displayed)
- **FG_PCT** - Field Goal Percentage (currently displayed)

### 2-Point Shooting Stats
- **FG2M** - 2-Point Field Goals Made (currently displayed)
- **FG2A** - 2-Point Field Goals Attempted (currently displayed)
- **FG2_PCT** - 2-Point Field Goal Percentage (currently displayed)

### 3-Point Shooting Stats
- **FG3M** - 3-Point Field Goals Made (currently displayed)
- **FG3A** - 3-Point Field Goals Attempted (currently displayed)
- **FG3_PCT** - 3-Point Field Goal Percentage (currently displayed)

## Potential Additional Stats (May be available but not confirmed)
Based on similar NBA API endpoints, these might also be available:
- Points per game from passes
- Free throw attempts/makes from passes
- Turnovers from passes
- Shot locations (restricted area, paint, mid-range, etc.)
- Time remaining on shot clock
- Pass distance
- Pass type (entry pass, kick-out, etc.)

## Current Page Features

1. **Team Selection** - Dropdown to select any NBA team
2. **Player Selection** - Two dropdowns:
   - Passer (player making passes)
   - Receiver (player receiving passes)
3. **Key Metrics Display** - 4 main metrics in columns
4. **Detailed Statistics Table** - Full breakdown for selected passer → receiver
5. **All Passing Relationships** - Complete list of all teammates the passer passes to, sorted by frequency

## Notes
- All stats are per-game averages (based on `per_mode_simple='PerGame'`)
- Stats can be filtered by season and season type
- Data is cached for 30 minutes (1800 seconds) to reduce API calls
- The page shows data for the current season (2025-26) by default

