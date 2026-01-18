"""
NBA Injury Report Fetcher
Fetches and parses official NBA injury reports from PDF.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
from datetime import datetime, date, timedelta
from io import BytesIO
from typing import Optional, Dict, List, Tuple
import re
import unicodedata

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("pdfplumber not installed. Run: pip install pdfplumber")

try:
    from unidecode import unidecode
    UNIDECODE_AVAILABLE = True
except ImportError:
    UNIDECODE_AVAILABLE = False
    print("unidecode not installed. Using unicodedata fallback. For better transliteration, run: pip install unidecode")


# Base URL for NBA injury reports
INJURY_REPORT_BASE_URL = "https://ak-static.cms.nba.com/referee/injury/"


def build_injury_report_url(report_date: date = None, hour: int = 1, minute: int = 0, period: str = "PM") -> str:
    """
    Build NBA injury report PDF URL.
    
    Args:
        report_date: Date of report (defaults to today)
        hour: Hour of report (1-12)
        minute: Minute of report (0, 15, 30, or 45)
        period: AM or PM
    
    Returns:
        URL string
    """
    if report_date is None:
        report_date = date.today()
    
    date_str = report_date.strftime('%Y-%m-%d')
    hour_str = f"{hour:02d}"
    minute_str = f"{minute:02d}"
    
    return f"{INJURY_REPORT_BASE_URL}Injury-Report_{date_str}_{hour_str}_{minute_str}{period}.pdf"


def try_fetch_injury_report(report_date: date = None) -> Tuple[Optional[bytes], str]:
    """
    Try to fetch injury report PDF, trying the most likely time first based on current time.
    
    Logic: Tries every 15 minutes (00, 15, 30, 45) going backwards from current time.
           Starts with the most recent 15-minute increment, then works backwards.
    
    Args:
        report_date: Date of report (defaults to today)
    
    Returns:
        Tuple of (PDF bytes or None, URL that worked or error message)
    """
    if report_date is None:
        report_date = date.today()
    
    # Get current time in ET (Eastern Time)
    try:
        import pytz
        et_tz = pytz.timezone('US/Eastern')
        now_et = datetime.now(et_tz)
    except ImportError:
        # Fallback if pytz not available - assume local is close to ET
        now_et = datetime.now()
    
    current_hour = now_et.hour
    current_minute = now_et.minute
    
    # Round down to nearest 15-minute increment
    rounded_minute = (current_minute // 15) * 15
    
    # Convert 24h to 12h format with AM/PM
    def hour_to_12h(h):
        if h == 0:
            return (12, "AM")
        elif h < 12:
            return (h, "AM")
        elif h == 12:
            return (12, "PM")
        else:
            return (h - 12, "PM")
    
    # Build list of times to try (most recent first, going backwards in 15-min increments)
    times_to_try = []
    
    # Start from current rounded time and go backwards
    start_datetime = now_et.replace(minute=rounded_minute, second=0, microsecond=0)
    
    # Create a datetime for 6 AM of the report date (in ET timezone)
    try:
        import pytz
        et_tz_check = pytz.timezone('US/Eastern')
        report_datetime_6am = et_tz_check.localize(datetime.combine(report_date, datetime.min.time()).replace(hour=6))
    except:
        report_datetime_6am = datetime.combine(report_date, datetime.min.time()).replace(hour=6)
    
    # Go back up to 24 hours, checking every 15 minutes
    for i in range(96):  # 24 hours * 4 (15-min intervals) = 96
        check_time = start_datetime - timedelta(minutes=i * 15)
        
        # Stop if we've gone back before 6 AM of the report date
        if check_time < report_datetime_6am:
            break
        
        hour_12, period = hour_to_12h(check_time.hour)
        minute = check_time.minute
        
        times_to_try.append((hour_12, minute, period))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_times = []
    for t in times_to_try:
        if t not in seen:
            seen.add(t)
            unique_times.append(t)
    
    for hour, minute, period in unique_times:
        url = build_injury_report_url(report_date, hour, minute, period)
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.content, url
        except requests.RequestException:
            continue
    
    return None, f"No injury report found for {report_date.strftime('%Y-%m-%d')}"


def get_team_abbreviation(team_name: str) -> str:
    """Get team abbreviation from team name."""
    if not team_name:
        return ""
    
    team_abbr_map = {
        'atlanta hawks': 'ATL',
        'boston celtics': 'BOS',
        'brooklyn nets': 'BKN',
        'charlotte hornets': 'CHA',
        'chicago bulls': 'CHI',
        'cleveland cavaliers': 'CLE',
        'dallas mavericks': 'DAL',
        'denver nuggets': 'DEN',
        'detroit pistons': 'DET',
        'golden state warriors': 'GSW',
        'houston rockets': 'HOU',
        'indiana pacers': 'IND',
        'la clippers': 'LAC',
        'los angeles clippers': 'LAC',
        'los angeles lakers': 'LAL',
        'memphis grizzlies': 'MEM',
        'miami heat': 'MIA',
        'milwaukee bucks': 'MIL',
        'minnesota timberwolves': 'MIN',
        'new orleans pelicans': 'NOP',
        'new york knicks': 'NYK',
        'oklahoma city thunder': 'OKC',
        'orlando magic': 'ORL',
        'philadelphia 76ers': 'PHI',
        'phoenix suns': 'PHX',
        'portland trail blazers': 'POR',
        'sacramento kings': 'SAC',
        'san antonio spurs': 'SAS',
        'toronto raptors': 'TOR',
        'utah jazz': 'UTA',
        'washington wizards': 'WAS',
    }
    
    return team_abbr_map.get(team_name.lower().strip(), "")


def parse_injury_report_pdf(pdf_bytes: bytes) -> pd.DataFrame:
    """
    Parse NBA injury report PDF into a DataFrame using text extraction.
    
    Args:
        pdf_bytes: Raw PDF content
    
    Returns:
        DataFrame with injury data
    """
    if not PDF_AVAILABLE:
        return pd.DataFrame()
    
    injuries = []
    
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
            
            if not full_text:
                return pd.DataFrame()
            
            # Parse the text line by line
            lines = full_text.split('\n')
            
            current_game_date = None
            current_game_time = None
            current_matchup = None
            current_team = None
            
            # Status keywords to identify injury lines
            status_keywords = ['Out', 'Questionable', 'Probable', 'Doubtful', 'Available']
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Skip headers and page markers
                if 'Injury Report:' in line or 'GameDate' in line or 'Page' in line:
                    continue
                if 'NOTYETSUBMITTED' in line or 'NOT YET SUBMITTED' in line:
                    continue
                
                # Check for matchup pattern (e.g., "NYK@ORL" or "SAS@OKC")
                matchup_match = re.search(r'([A-Z]{3})@([A-Z]{3})', line)
                if matchup_match:
                    current_matchup = matchup_match.group(0)
                
                # Check if line starts with a date (MM/DD/YYYY)
                date_match = re.match(r'^(\d{1,2}/\d{1,2}/\d{4})', line)
                if date_match:
                    current_game_date = date_match.group(1)
                    # Find the time (contains ET)
                    time_match = re.search(r'(\d{2}:\d{2}\(ET\))', line)
                    if time_match:
                        current_game_time = time_match.group(1)
                    # Remove date/time/matchup from line for further processing
                    line = re.sub(r'^\d{1,2}/\d{1,2}/\d{4}\s+\d{2}:\d{2}\(ET\)\s+[A-Z]{3}@[A-Z]{3}\s*', '', line)
                
                # Check if line contains a team name (no space before team name in PDF)
                team_patterns = [
                    ('NewYorkKnicks', 'New York Knicks'),
                    ('OrlandoMagic', 'Orlando Magic'),
                    ('SanAntonioSpurs', 'San Antonio Spurs'),
                    ('OklahomaCityThunder', 'Oklahoma City Thunder'),
                    ('BostonCeltics', 'Boston Celtics'),
                    ('LosAngelesLakers', 'Los Angeles Lakers'),
                    ('GoldenStateWarriors', 'Golden State Warriors'),
                    ('MiamiHeat', 'Miami Heat'),
                    ('PhoenixSuns', 'Phoenix Suns'),
                    ('DallasMavericks', 'Dallas Mavericks'),
                    ('MilwaukeeBucks', 'Milwaukee Bucks'),
                    ('PhiladelphiaPhiladelphia76ers', 'Philadelphia 76ers'),
                    ('Philadelphia76ers', 'Philadelphia 76ers'),
                    ('AtlantaHawks', 'Atlanta Hawks'),
                    ('ChicagoBulls', 'Chicago Bulls'),
                    ('ClevelandCavaliers', 'Cleveland Cavaliers'),
                    ('DetroitPistons', 'Detroit Pistons'),
                    ('IndianaPacers', 'Indiana Pacers'),
                    ('CharlotteHornets', 'Charlotte Hornets'),
                    ('TorontoRaptors', 'Toronto Raptors'),
                    ('WashingtonWizards', 'Washington Wizards'),
                    ('BrooklynNets', 'Brooklyn Nets'),
                    ('NewOrleansPelicans', 'New Orleans Pelicans'),
                    ('MemphisGrizzlies', 'Memphis Grizzlies'),
                    ('MinnesotaTimberwolves', 'Minnesota Timberwolves'),
                    ('HoustonRockets', 'Houston Rockets'),
                    ('DenverNuggets', 'Denver Nuggets'),
                    ('UtahJazz', 'Utah Jazz'),
                    ('PortlandTrailBlazers', 'Portland Trail Blazers'),
                    ('SacramentoKings', 'Sacramento Kings'),
                    ('LAClippers', 'LA Clippers'),
                ]
                
                for pattern, team_name in team_patterns:
                    if pattern in line:
                        current_team = team_name
                        # Remove team name from line to get player info
                        line = line.replace(pattern, '').strip()
                        break
                
                # Now try to extract player info
                # Look for status keyword in line
                found_status = None
                status_pos = -1
                for status in status_keywords:
                    if status in line:
                        found_status = status
                        status_pos = line.find(status)
                        break
                
                if found_status and status_pos > 0:
                    # Player name is before status
                    player_part = line[:status_pos].strip()
                    # Reason is after status
                    reason_part = line[status_pos + len(found_status):].strip()
                    
                    # Clean up player name - remove any date/time/matchup that might be stuck
                    player_name = player_part
                    player_name = re.sub(r'^\d{1,2}/\d{1,2}/\d{4}\s*', '', player_name)
                    player_name = re.sub(r'^\d{2}:\d{2}\(ET\)\s*', '', player_name)
                    player_name = re.sub(r'^[A-Z]{3}@[A-Z]{3}\s*', '', player_name)
                    player_name = player_name.strip()
                    
                    # Skip if empty or looks like header
                    if not player_name or any(x in player_name.lower() for x in ['gamedate', 'gametime', 'matchup', 'page']):
                        continue
                    
                    # Clean up reason
                    reason = reason_part.replace('Injury/Illness-', '').replace('Injury/Illness', '').strip()
                    if reason.startswith('-'):
                        reason = reason[1:].strip()
                    
                    # Determine the correct matchup for this team
                    # Only use current_matchup if the team is actually in that matchup
                    team_matchup = current_matchup
                    if current_team and current_matchup:
                        # Get team abbreviation for current team
                        team_abbr = get_team_abbreviation(current_team)
                        if team_abbr and team_abbr not in current_matchup:
                            # This team is not in the current matchup - need to find correct one
                            team_matchup = None  # Will be matched later by team name
                    
                    injuries.append({
                        'game_date': current_game_date,
                        'game_time': current_game_time,
                        'matchup': team_matchup,
                        'team': current_team,
                        'player_name': player_name,
                        'status': found_status,
                        'reason': reason
                    })
    
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()
    
    return pd.DataFrame(injuries)


def normalize_player_name(name: str) -> str:
    """Normalize player name for matching."""
    if not name:
        return ""
    
    # Common suffixes to handle
    suffixes = ['Jr.', 'Jr', 'Sr.', 'Sr', 'II', 'III', 'IV', 'V']
    
    # Add space before suffixes that might be attached (e.g., "PorterJr." -> "Porter Jr.")
    for suffix in suffixes:
        # Handle case like "PorterJr." -> "Porter Jr."
        name = re.sub(rf'([a-z])({re.escape(suffix)})', rf'\1 \2', name, flags=re.IGNORECASE)
    
    # Convert "Last, First" to "First Last"
    if ',' in name:
        parts = name.split(',')
        if len(parts) == 2:
            last_part = parts[0].strip()
            first_part = parts[1].strip()
            name = f"{first_part} {last_part}"
    
    # Clean up multiple spaces
    name = re.sub(r'\s+', ' ', name).strip()
    
    # Apply ASCII normalization to handle special characters
    # This ensures "Jokić" and "Jokic" both normalize to "jokic"
    name = normalize_to_ascii(name)
    
    return name.lower().strip()


def normalize_to_ascii(text: str) -> str:
    """
    Normalize Unicode text to ASCII equivalent for matching.
    
    Converts special characters to their ASCII equivalents:
    - "Jokić" → "Jokic"
    - "Valančiūnas" → "Valanciunas"
    - "Dončić" → "Doncic"
    
    Args:
        text: Input string that may contain Unicode characters
    
    Returns:
        Lowercase ASCII string
    """
    if not text:
        return ""
    
    if UNIDECODE_AVAILABLE:
        # Use unidecode for better transliteration
        return unidecode(text).lower()
    else:
        # Fallback to unicodedata normalization
        # Normalize to NFD (decomposed form), then remove combining characters
        normalized = unicodedata.normalize('NFD', text)
        # Filter out combining characters (diacritics) and convert to ASCII
        ascii_text = ''.join(
            char for char in normalized 
            if unicodedata.category(char) != 'Mn'  # Mn = Mark, nonspacing (diacritics)
        )
        # Encode to ASCII, ignoring non-ASCII characters, then decode back
        return ascii_text.encode('ascii', 'ignore').decode('ascii').lower()


def match_player_to_id(
    player_name: str,
    players_df: pd.DataFrame,
    team_name: str = None
) -> Optional[str]:
    """
    Match a player name from injury report to a player ID.
    
    Args:
        player_name: Name from injury report (may be "Last, First" format)
        players_df: DataFrame with PERSON_ID, PLAYER_FIRST_NAME, PLAYER_LAST_NAME
        team_name: Optional team name to narrow search
    
    Returns:
        Player ID as string, or None if no match
    """
    if players_df is None or len(players_df) == 0:
        return None
    
    normalized_name = normalize_player_name(player_name)
    
    # Try to filter by team first if provided
    search_df = players_df.copy()
    if team_name:
        # Try matching team name
        team_match = search_df[
            search_df['TEAM_NAME'].str.lower().str.contains(team_name.lower().split()[-1], na=False) |
            search_df['TEAM_CITY'].str.lower().str.contains(team_name.lower().split()[0], na=False)
        ]
        if len(team_match) > 0:
            search_df = team_match
    
    # Create full name column for matching with ASCII normalization
    search_df = search_df.copy()
    search_df['full_name_lower'] = (
        search_df['PLAYER_FIRST_NAME'].fillna('').str.lower() + ' ' +
        search_df['PLAYER_LAST_NAME'].fillna('').str.lower()
    ).str.strip()
    # Apply ASCII normalization to database names for comparison
    search_df['full_name_lower'] = search_df['full_name_lower'].apply(normalize_to_ascii)
    
    # Try exact match first
    exact_match = search_df[search_df['full_name_lower'] == normalized_name]
    if len(exact_match) > 0:
        return str(exact_match['PERSON_ID'].iloc[0])
    
    # Try last name match
    # Handle suffixes like Jr., Sr., II, III when extracting last name
    suffixes_lower = ['jr.', 'jr', 'sr.', 'sr', 'ii', 'iii', 'iv', 'v']
    
    last_name_with_suffix = None  # Keep track of full last name with suffix
    
    if ',' in player_name:
        last_name_raw = player_name.split(',')[0].strip().lower()
        last_name = last_name_raw
        
        # Check if suffix is attached and extract both versions
        for suffix in suffixes_lower:
            if last_name.endswith(suffix):
                # Add space before suffix for "with suffix" version
                last_name_with_suffix = last_name[:-len(suffix)].strip() + ' ' + suffix
                last_name = last_name[:-len(suffix)].strip()
                break
        # Also handle space before suffix
        for suffix in suffixes_lower:
            if f' {suffix}' in last_name:
                last_name_with_suffix = last_name  # Already has space
                last_name = last_name.replace(f' {suffix}', '').strip()
                break
    else:
        # For "First Last Jr." format, get the actual last name (not the suffix)
        name_parts = player_name.split()
        if len(name_parts) >= 2:
            # Check if last part is a suffix
            last_part_clean = name_parts[-1].lower().rstrip('.')
            if last_part_clean in [s.rstrip('.') for s in suffixes_lower]:
                last_name = name_parts[-2].lower() if len(name_parts) >= 2 else name_parts[-1].lower()
                # Build "last name + suffix" version (e.g., "pippen jr.")
                last_name_with_suffix = f"{last_name} {name_parts[-1].lower()}"
            else:
                last_name = name_parts[-1].lower()
        else:
            last_name = player_name.lower()
    
    # Normalize last names to ASCII for comparison
    # Normalize the search last names (from injury report)
    last_name_normalized = normalize_to_ascii(last_name)
    last_name_with_suffix_normalized = normalize_to_ascii(last_name_with_suffix) if last_name_with_suffix else None
    
    # Create normalized last name column for database names
    search_df['last_name_normalized'] = search_df['PLAYER_LAST_NAME'].fillna('').str.lower().apply(normalize_to_ascii)
    
    # Try matching with suffix first (since that's how NBA stores it, e.g., "Pippen Jr.")
    if last_name_with_suffix_normalized:
        last_name_match = search_df[search_df['last_name_normalized'] == last_name_with_suffix_normalized]
        if len(last_name_match) == 0:
            # Also try with period variations
            last_name_with_suffix_no_period = last_name_with_suffix_normalized.replace('.', '')
            last_name_match = search_df[
                search_df['last_name_normalized'].str.replace('.', '', regex=False) == last_name_with_suffix_no_period
            ]
    else:
        last_name_match = pd.DataFrame()
    
    # If no match with suffix, try without suffix
    if len(last_name_match) == 0:
        last_name_match = search_df[search_df['last_name_normalized'] == last_name_normalized]
    
    if len(last_name_match) == 1:
        return str(last_name_match['PERSON_ID'].iloc[0])
    elif len(last_name_match) > 1:
        # Multiple matches - try to narrow with first name
        if ',' in player_name:
            first_name = player_name.split(',')[1].strip().lower()
        else:
            first_name = player_name.split()[0].lower() if ' ' in player_name else ''
        
        if first_name:
            # Normalize first name to ASCII for comparison
            first_name_normalized = normalize_to_ascii(first_name)
            # Create normalized first name column for database names
            last_name_match['first_name_normalized'] = last_name_match['PLAYER_FIRST_NAME'].fillna('').str.lower().apply(normalize_to_ascii)
            
            first_match = last_name_match[
                last_name_match['first_name_normalized'].str.startswith(first_name_normalized[:3])
            ]
            if len(first_match) > 0:
                return str(first_match['PERSON_ID'].iloc[0])
        
        # Return first match if still multiple
        return str(last_name_match['PERSON_ID'].iloc[0])
    
    return None


def get_injuries_for_matchup(
    injury_df: pd.DataFrame,
    away_team_abbr: str,
    home_team_abbr: str,
    players_df: pd.DataFrame
) -> Dict[str, List[Dict]]:
    """
    Get injury data for a specific matchup.
    
    Args:
        injury_df: DataFrame from parse_injury_report_pdf
        away_team_abbr: Away team abbreviation (e.g., 'NYK')
        home_team_abbr: Home team abbreviation (e.g., 'ORL')
        players_df: Players DataFrame for ID matching
    
    Returns:
        Dict with 'away' and 'home' keys, each containing list of injury dicts
    """
    # #region agent log
    with open('/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log', 'a') as f:
        import json
        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "injury_report.py:554", "message": "get_injuries_for_matchup entry", "data": {"injury_df_len": len(injury_df) if injury_df is not None else 0, "away_team": away_team_abbr, "home_team": home_team_abbr}, "timestamp": int(__import__('time').time() * 1000)}) + '\n')
    # #endregion
    result = {'away': [], 'home': []}
    
    if injury_df is None or len(injury_df) == 0:
        # #region agent log
        with open('/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log', 'a') as f:
            import json
            f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "injury_report.py:575", "message": "get_injuries_for_matchup: Empty injury_df, returning early", "data": {}, "timestamp": int(__import__('time').time() * 1000)}) + '\n')
        # #endregion
        return result
    
    # Build matchup pattern (e.g., "NYK@ORL" or "NYK @ ORL")
    # Only match exact matchup patterns - both teams must be present
    matchup_patterns = [
        f"{away_team_abbr}@{home_team_abbr}",
        f"{away_team_abbr} @ {home_team_abbr}",
        f"{away_team_abbr}vs{home_team_abbr}",
        f"{away_team_abbr} vs {home_team_abbr}",
        f"{home_team_abbr}@{away_team_abbr}",  # Reverse order just in case
        f"{home_team_abbr} @ {away_team_abbr}",
        f"{home_team_abbr}vs{away_team_abbr}",
        f"{home_team_abbr} vs {away_team_abbr}",
    ]
    
    # Find matching rows - must be one of the teams in this matchup
    # Match by TEAM NAME, not by matchup string (more reliable)
    def team_in_matchup(team_name):
        if not team_name:
            return False
        team_abbr = get_team_abbreviation(team_name)
        if not team_abbr:
            return False
        # Check if this team is in the requested matchup
        return team_abbr.upper() == away_team_abbr.upper() or team_abbr.upper() == home_team_abbr.upper()
    
    # #region agent log
    with open('/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log', 'a') as f:
        import json
        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "injury_report.py:601", "message": "get_injuries_for_matchup: Before filtering injuries", "data": {"injury_df_len": len(injury_df)}, "timestamp": int(__import__('time').time() * 1000)}) + '\n')
    # #endregion
    matchup_injuries = injury_df[injury_df['team'].apply(team_in_matchup)]
    # #region agent log
    with open('/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log', 'a') as f:
        import json
        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "injury_report.py:603", "message": "get_injuries_for_matchup: After filtering injuries", "data": {"matchup_injuries_len": len(matchup_injuries)}, "timestamp": int(__import__('time').time() * 1000)}) + '\n')
    # #endregion
    
    if len(matchup_injuries) == 0:
        return result
    
    # #region agent log
    with open('/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log', 'a') as f:
        import json
        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "injury_report.py:606", "message": "get_injuries_for_matchup: Starting to iterate injuries", "data": {"injury_count": len(matchup_injuries)}, "timestamp": int(__import__('time').time() * 1000)}) + '\n')
    # #endregion
    
    for idx, (_, row) in enumerate(matchup_injuries.iterrows()):
        # #region agent log
        if idx < 5 or idx % 10 == 0:  # Log first 5 and every 10th
            with open('/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log', 'a') as f:
                import json
                f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "injury_report.py:608", "message": f"get_injuries_for_matchup: Processing injury {idx}", "data": {"player_name": str(row.get('player_name', ''))}, "timestamp": int(__import__('time').time() * 1000)}) + '\n')
        # #endregion
        player_name = row['player_name']
        team = row['team']
        status = row['status']
        reason = row['reason']
        
        # Match player to ID
        # #region agent log
        with open('/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log', 'a') as f:
            import json
            f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "injury_report.py:613", "message": f"get_injuries_for_matchup: Before match_player_to_id", "data": {"player_name": str(player_name)}, "timestamp": int(__import__('time').time() * 1000)}) + '\n')
        # #endregion
        player_id = match_player_to_id(player_name, players_df, team)
        # #region agent log
        with open('/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log', 'a') as f:
            import json
            f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "injury_report.py:620", "message": f"get_injuries_for_matchup: After match_player_to_id", "data": {"player_id": str(player_id) if player_id else None}, "timestamp": int(__import__('time').time() * 1000)}) + '\n')
        # #endregion
        
        injury_info = {
            'player_name': player_name,
            'player_id': player_id,
            'status': status,
            'reason': reason,
            'team': team
        }
        
        # Team name to abbreviation mapping
        team_abbr_map = {
            'hawks': 'ATL', 'atlanta': 'ATL',
            'celtics': 'BOS', 'boston': 'BOS',
            'nets': 'BKN', 'brooklyn': 'BKN',
            'hornets': 'CHA', 'charlotte': 'CHA',
            'bulls': 'CHI', 'chicago': 'CHI',
            'cavaliers': 'CLE', 'cleveland': 'CLE',
            'mavericks': 'DAL', 'dallas': 'DAL',
            'nuggets': 'DEN', 'denver': 'DEN',
            'pistons': 'DET', 'detroit': 'DET',
            'warriors': 'GSW', 'golden state': 'GSW',
            'rockets': 'HOU', 'houston': 'HOU',
            'pacers': 'IND', 'indiana': 'IND',
            'clippers': 'LAC', 'la clippers': 'LAC',
            'lakers': 'LAL', 'los angeles lakers': 'LAL',
            'grizzlies': 'MEM', 'memphis': 'MEM',
            'heat': 'MIA', 'miami': 'MIA',
            'bucks': 'MIL', 'milwaukee': 'MIL',
            'timberwolves': 'MIN', 'minnesota': 'MIN',
            'pelicans': 'NOP', 'new orleans': 'NOP',
            'knicks': 'NYK', 'new york knicks': 'NYK',
            'thunder': 'OKC', 'oklahoma city': 'OKC', 'oklahoma': 'OKC',
            'magic': 'ORL', 'orlando': 'ORL',
            '76ers': 'PHI', 'sixers': 'PHI', 'philadelphia': 'PHI',
            'suns': 'PHX', 'phoenix': 'PHX',
            'trail blazers': 'POR', 'blazers': 'POR', 'portland': 'POR',
            'kings': 'SAC', 'sacramento': 'SAC',
            'spurs': 'SAS', 'san antonio': 'SAS',
            'raptors': 'TOR', 'toronto': 'TOR',
            'jazz': 'UTA', 'utah': 'UTA',
            'wizards': 'WAS', 'washington': 'WAS',
        }
        
        # Determine if away or home team
        team_lower = team.lower() if team else ''
        matched_abbr = None
        
        # Try to find team abbreviation from team name
        for name_key, abbr in team_abbr_map.items():
            if name_key in team_lower:
                matched_abbr = abbr
                break
        
        # Assign to away or home based on matched abbreviation
        if matched_abbr == away_team_abbr:
            result['away'].append(injury_info)
        elif matched_abbr == home_team_abbr:
            result['home'].append(injury_info)
        elif team and away_team_abbr.lower() in team_lower:
            result['away'].append(injury_info)
        elif team and home_team_abbr.lower() in team_lower:
            result['home'].append(injury_info)
        else:
            # Default: use first word of team name and try to match
            # This is a fallback - log it for debugging
            print(f"Could not match team '{team}' to {away_team_abbr} or {home_team_abbr}")
            result['away'].append(injury_info)  # Fallback to away
    
    return result


def get_players_out_for_matchup(
    injury_df: pd.DataFrame,
    away_team_abbr: str,
    home_team_abbr: str,
    players_df: pd.DataFrame
) -> Dict[str, List[str]]:
    """
    Get list of player IDs who are OUT for a matchup.
    
    Returns:
        Dict with 'away_out' and 'home_out' keys containing player ID lists
    """
    result = {'away_out': [], 'home_out': []}
    
    injuries = get_injuries_for_matchup(
        injury_df, away_team_abbr, home_team_abbr, players_df
    )
    
    for inj in injuries['away']:
        if inj['status'] == 'Out' and inj['player_id']:
            result['away_out'].append(inj['player_id'])
    
    for inj in injuries['home']:
        if inj['status'] == 'Out' and inj['player_id']:
            result['home_out'].append(inj['player_id'])
    
    return result


def fetch_injuries_for_date(report_date: date = None, players_df: pd.DataFrame = None) -> Tuple[pd.DataFrame, str]:
    """
    Fetch and parse injury report for a specific date.
    Tries multiple recent report times going backwards from current time.
    
    Args:
        report_date: Date to fetch injuries for (defaults to today)
        players_df: Optional players DataFrame (not used in this function but kept for compatibility)
    
    Returns:
        Tuple of (injury DataFrame, status message)
    """
    if report_date is None:
        report_date = date.today()
    
    # Always use today's date for URL construction (injury report PDF includes tomorrow's games too)
    url_date = date.today()
    
    # #region agent log
    with open('/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log', 'a') as f:
        import json
        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "injury_report.py:756", "message": "fetch_injuries_for_date entry", "data": {"report_date": str(report_date), "url_date": str(url_date)}, "timestamp": int(__import__('time').time() * 1000)}) + '\n')
    # #endregion
    
    # Get current time in ET (Eastern Time)
    try:
        import pytz
        et_tz = pytz.timezone('US/Eastern')
        now_et = datetime.now(et_tz)
    except ImportError:
        now_et = datetime.now()
    
    current_hour = now_et.hour
    current_minute = now_et.minute
    
    # Round down to nearest 15-minute increment
    rounded_minute = (current_minute // 15) * 15
    
    # Convert 24h to 12h format with AM/PM
    def hour_to_12h(h):
        if h == 0:
            return (12, "AM")
        elif h < 12:
            return (h, "AM")
        elif h == 12:
            return (12, "PM")
        else:
            return (h - 12, "PM")
    
    # Build list of times to try (most recent first, going backwards)
    # Try only the last hour (4 attempts: current, 15min, 30min, 45min back)
    times_to_try = []
    
    # Always use current time rounded down (URL always uses today's date)
    start_datetime = now_et.replace(minute=rounded_minute, second=0, microsecond=0)
    
    # Go back only 1 hour (4 attempts), checking every 15 minutes
    for i in range(4):  # 1 hour * 4 (15-min intervals) = 4 attempts
        check_time = start_datetime - timedelta(minutes=i * 15)
        
        # Stop if we've gone back before today (don't check previous days)
        if check_time.date() < url_date:
            break
        
        hour_12, period = hour_to_12h(check_time.hour)
        minute = check_time.minute
        
        times_to_try.append((hour_12, minute, period, check_time))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_times = []
    for t in times_to_try:
        time_key = (t[0], t[1], t[2])
        if time_key not in seen:
            seen.add(time_key)
            unique_times.append(t)
    
    # #region agent log
    with open('/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log', 'a') as f:
        import json
        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "injury_report.py:800", "message": "fetch_injuries_for_date: Starting URL attempts", "data": {"num_times_to_try": len(unique_times), "first_time": f"{unique_times[0][0]:02d}:{unique_times[0][1]:02d}{unique_times[0][2]}" if unique_times else None}, "timestamp": int(__import__('time').time() * 1000)}) + '\n')
    # #endregion
    
    tried_urls = []
    for idx, (hour_12, minute, period, check_time) in enumerate(unique_times):
        # Always use today's date for URL (injury report PDF includes tomorrow's games too)
        url = build_injury_report_url(url_date, hour_12, minute, period)
        time_str = f"{hour_12:02d}:{minute:02d}{period}"
        tried_urls.append(time_str)
        
        # #region agent log
        if idx < 5 or idx % 5 == 0:  # Log first 5 and every 5th attempt
            with open('/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log', 'a') as f:
                import json
                f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "injury_report.py:810", "message": f"fetch_injuries_for_date: Attempt {idx+1}/{len(unique_times)}", "data": {"time_str": time_str, "url": url}, "timestamp": int(__import__('time').time() * 1000)}) + '\n')
        # #endregion
        
        try:
            # Create session with retry strategy and proper headers
            session = requests.Session()
            retry_strategy = Retry(
                total=2,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET"]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("https://", adapter)
            
            # Use proper User-Agent header (some CDNs block generic clients)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/pdf',
                'Accept-Language': 'en-US,en;q=0.9'
            }
            
            # GET request with proper timeout settings: (connect_timeout, read_timeout)
            # Separate timeouts: 5s to connect, 30s to read
            response = session.get(url, headers=headers, timeout=(5, 30), allow_redirects=True)
            
            # #region agent log
            with open('/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log', 'a') as f:
                import json
                response_text_preview = response.text[:200] if hasattr(response, 'text') and response.text else ""
                f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "injury_report.py:825", "message": f"fetch_injuries_for_date: GET response for {time_str}", "data": {"status_code": response.status_code, "url": url, "content_length": len(response.content) if response.content else 0, "response_preview": response_text_preview}, "timestamp": int(__import__('time').time() * 1000)}) + '\n')
            # #endregion
            
            # Handle different status codes
            if response.status_code == 403:
                # 403 Forbidden - might mean URL doesn't exist yet or server is blocking
                # #region agent log
                with open('/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log', 'a') as f:
                    import json
                    response_text = response.text[:500] if hasattr(response, 'text') and response.text else ""
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "injury_report.py:830", "message": f"fetch_injuries_for_date: 403 Forbidden for {time_str}", "data": {"url": url, "response_text": response_text}, "timestamp": int(__import__('time').time() * 1000)}) + '\n')
                # #endregion
                continue  # Skip to next time
            elif response.status_code == 404:
                # 404 Not Found - URL doesn't exist
                # #region agent log
                with open('/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "injury_report.py:837", "message": f"fetch_injuries_for_date: 404 Not Found for {time_str}", "data": {"url": url}, "timestamp": int(__import__('time').time() * 1000)}) + '\n')
                # #endregion
                continue  # Skip to next time
            
            if response.status_code == 200:
                # Try to parse the PDF
                injury_df = parse_injury_report_pdf(response.content)
                
                # #region agent log
                with open('/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "injury_report.py:833", "message": f"fetch_injuries_for_date: Parsed PDF for {time_str}", "data": {"injury_count": len(injury_df) if injury_df is not None else 0}, "timestamp": int(__import__('time').time() * 1000)}) + '\n')
                # #endregion
                
                if len(injury_df) > 0:
                    return injury_df, f"✅ Loaded {len(injury_df)} injuries from **{time_str} ET** report ([source]({url}))"
        
        except requests.Timeout as e:
            # #region agent log
            with open('/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log', 'a') as f:
                import json
                f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "injury_report.py:842", "message": f"fetch_injuries_for_date: Timeout for {time_str}", "data": {"error": str(e), "error_type": "Timeout"}, "timestamp": int(__import__('time').time() * 1000)}) + '\n')
            # #endregion
            # Add small delay before next attempt to avoid overwhelming server
            import time
            time.sleep(0.5)
            continue
        except requests.RequestException as e:
            # #region agent log
            with open('/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log', 'a') as f:
                import json
                f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "injury_report.py:848", "message": f"fetch_injuries_for_date: RequestException for {time_str}", "data": {"error": str(e), "error_type": type(e).__name__}, "timestamp": int(__import__('time').time() * 1000)}) + '\n')
            # #endregion
            continue
    
    # #region agent log
    with open('/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log', 'a') as f:
        import json
        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "injury_report.py:838", "message": "fetch_injuries_for_date: All attempts failed", "data": {"num_attempts": len(tried_urls), "tried_times": tried_urls[:10]}, "timestamp": int(__import__('time').time() * 1000)}) + '\n')
    # #endregion
    
    # If none of the times worked, return empty
    return pd.DataFrame(), f"❌ No injury report found for {report_date.strftime('%m/%d/%Y')}. Tried: {', '.join(tried_urls[:5])}..."


def fetch_todays_injuries(players_df: pd.DataFrame = None) -> Tuple[pd.DataFrame, str]:
    """
    Convenience function to fetch and parse today's injury report.
    Wrapper around fetch_injuries_for_date() for backwards compatibility.
    
    Returns:
        Tuple of (injury DataFrame, status message)
    """
    return fetch_injuries_for_date(report_date=date.today(), players_df=players_df)


def format_injury_status(status: str) -> str:
    """Format injury status with emoji."""
    status_lower = status.lower() if status else ''
    if 'out' in status_lower:
        return '🔴 Out'
    elif 'questionable' in status_lower:
        return '🟡 Questionable'
    elif 'probable' in status_lower:
        return '🟢 Probable'
    elif 'doubtful' in status_lower:
        return '🟠 Doubtful'
    elif 'available' in status_lower:
        return '✅ Available'
    return status


def format_player_name(name: str) -> str:
    """
    Format player name from 'Last,First' to 'First Last'.
    Also handles names like 'JonesGarcia,David' -> 'David Jones Garcia'
    """
    if not name:
        return name
    
    name = name.strip()
    
    if ',' in name:
        parts = name.split(',')
        if len(parts) == 2:
            last_name = parts[0].strip()
            first_name = parts[1].strip()
            
            # Add spaces to camelCase last names (e.g., "JonesGarcia" -> "Jones Garcia")
            last_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', last_name)
            
            return f"{first_name} {last_name}"
    
    return name


def format_injury_reason(reason: str) -> str:
    """
    Format injury reason to be more readable.
    E.g., 'LeftCalf;Strain' -> 'Left Calf Strain'
    """
    if not reason:
        return ""
    
    reason = reason.strip()
    
    # Remove leading dashes or semicolons
    reason = re.sub(r'^[-;]+', '', reason)
    
    # Add spaces before capital letters (camelCase -> separate words)
    reason = re.sub(r'([a-z])([A-Z])', r'\1 \2', reason)
    
    # Replace semicolons with spaces
    reason = reason.replace(';', ' ')
    
    # Clean up multiple spaces
    reason = re.sub(r'\s+', ' ', reason).strip()
    
    return reason


def format_injury_display(player_name: str, status: str, reason: str) -> str:
    """
    Format a complete injury display line.
    E.g., 'Victor Wembanyama | 🟢 Probable | Left Calf Strain'
    """
    formatted_name = format_player_name(player_name)
    formatted_status = format_injury_status(status)
    formatted_reason = format_injury_reason(reason)
    
    if formatted_reason:
        return f"{formatted_name} | {formatted_status} | {formatted_reason}"
    else:
        return f"{formatted_name} | {formatted_status}"

