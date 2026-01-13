# Sportradar API Integration Setup Guide

## Overview

This guide explains how to set up and use the Sportradar API integration as an alternative to the NBA API.

## Prerequisites

1. **Sportradar API Keys**: You need API keys for:
   - Sportradar NBA API
   - Sportradar Synergy Basketball API
   - Sportradar Global Basketball API (optional)

2. **Supabase Database**: The `sr_*` tables must be created (run migration `005_sportradar_tables.sql`)

## Setup Steps

### 1. Add API Keys to .env File

Add the following to your `.env` file:

```env
# Sportradar API Keys
SPORTRADAR_NBA_API_KEY=your_nba_api_key_here
SPORTRADAR_SYNERGY_API_KEY=your_synergy_api_key_here
SPORTRADAR_GLOBAL_API_KEY=your_global_api_key_here
```

### 2. Run Supabase Migration

Execute the migration file to create the `sr_*` tables:

```sql
-- Run in Supabase SQL Editor
-- File: supabase/migrations/005_sportradar_tables.sql
```

### 3. Fetch Data from Sportradar APIs

Run the fetch scripts to populate the database:

```bash
# Test individual scripts first
python scripts/sportradar_fetch_schedule.py
python scripts/sportradar_fetch_synergy_data.py
python scripts/sportradar_fetch_game_logs.py

# Or run all scripts
python scripts/sportradar_fetch_team_stats.py
python scripts/sportradar_fetch_player_stats.py
python scripts/sportradar_fetch_standings.py
python scripts/sportradar_fetch_player_index.py
```

### 4. Compare Data Structures

Run the comparison script to validate data mapping:

```bash
python scripts/compare_sportradar_nba_api.py
```

This will generate `docs/sportradar_mapping.md` with field mappings.

### 5. Validate Data Quality

Run the validation script:

```bash
python scripts/validate_sportradar_data.py
```

This will generate `docs/sportradar_validation_report.md`.

### 6. Test the Test Page

Navigate to the test page in your Streamlit app:

```
http://localhost:8520/Teams_Sportradar
```

## API Endpoint Notes

### Sportradar NBA API
- Base URL: `https://api.sportradar.com/nba/{version}/`
- Authentication: API key as query parameter
- Version: Check your subscription (typically v8)

### Sportradar Synergy Basketball API
- Base URL: `https://api.sportradar.com/synergy/{version}/`
- Authentication: API key as query parameter
- Version: Check your subscription (typically v1)

### Endpoint Formats

**Schedule:**
```
/games/{year}/REG/schedule
```

**Standings:**
```
/seasons/{year}/standings
```

**Seasonal Statistics:**
```
/seasons/{year}/teams/statistics
/seasons/{year}/players/statistics
```

**Synergy Playtype Stats:**
```
/play-type-stats/team/{season}/{playtype}/{type_grouping}
/play-type-stats/player/{season}/{playtype}/offensive
```

**Daily Summaries:**
```
/games/{year}/{month}/{day}/summary
```

## Quota Management

Each API has a 1,000 call quota. Estimated daily usage:

- **Schedule**: ~1 call/day
- **Synergy**: ~33 calls/day (team: 22, player: 11)
- **Game Logs**: ~1 call/day (daily summaries)
- **Team Stats**: ~12 calls/day
- **Player Stats**: ~1 call/day
- **Standings**: ~1 call/day
- **Player Index**: ~1 call/day

**Total**: ~50 calls/day = ~20 days of quota per API

## Data Mapping

Field names between NBA API and Sportradar API may differ. Use the comparison script to identify mappings:

- `compare_sportradar_nba_api.py` - Compares data structures
- `docs/sportradar_mapping.md` - Documents field mappings

## Known Limitations

1. **Clutch Stats**: May not be directly available - may need custom calculation
2. **On/Off Court Data**: May not be available in Sportradar API
3. **Drives Stats**: May need to calculate from play-by-play data
4. **Field Name Differences**: Field names will differ - mapping required

## Troubleshooting

### API Key Issues
- Verify API keys are set in `.env` file
- Check API key format (no quotes, no extra spaces)
- Verify API keys are active in Sportradar dashboard

### Data Not Loading
- Check Supabase tables exist (`sr_*` tables)
- Verify data was fetched successfully (check Supabase dashboard)
- Check logs for API errors

### Field Mapping Issues
- Run comparison script to see actual field names
- Update mapping documentation as needed
- Adjust data reader functions to match actual API structure

## Next Steps

1. ✅ Configuration module created
2. ✅ Database tables created
3. ✅ Fetch scripts created
4. ✅ Data reader module created
5. ✅ Test page created
6. ⏳ Fetch actual data and validate
7. ⏳ Map fields to match NBA API structure
8. ⏳ Update app to use Sportradar data

