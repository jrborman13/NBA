"""
Sportradar API Configuration Module
Handles API keys and client initialization for Sportradar APIs.
Supports NBA API, Synergy Basketball API, and Global Basketball API.
"""

import os
from typing import Optional
from dotenv import load_dotenv
import logging
import sys
from pathlib import Path

# Load environment variables
project_root = Path(__file__).parent.parent.parent
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
else:
    load_dotenv()

logger = logging.getLogger(__name__)

# Sportradar API configuration from environment variables
# Strip whitespace and quotes if present
SPORTRADAR_NBA_API_KEY = os.getenv("SPORTRADAR_NBA_API_KEY", "").strip().strip('"').strip("'")
SPORTRADAR_SYNERGY_API_KEY = os.getenv("SPORTRADAR_SYNERGY_API_KEY", "").strip().strip('"').strip("'")
SPORTRADAR_GLOBAL_API_KEY = os.getenv("SPORTRADAR_GLOBAL_API_KEY", "").strip().strip('"').strip("'")

# Sportradar API base URLs
# Try both .com and .us domains (documentation shows .us for some endpoints)
SPORTRADAR_NBA_BASE_URL = "https://api.sportradar.com/nba"
SPORTRADAR_NBA_BASE_URL_US = "https://api.sportradar.us/nba"  # Alternative domain
SPORTRADAR_SYNERGY_BASE_URL = "https://api.sportradar.com/synergy"
SPORTRADAR_GLOBAL_BASE_URL = "https://api.sportradar.com/basketball"

# API version (adjust based on your subscription)
SPORTRADAR_NBA_VERSION = "v8"  # Check your subscription for correct version
SPORTRADAR_SYNERGY_VERSION = "v1"  # Check your subscription for correct version
SPORTRADAR_GLOBAL_VERSION = "v2"  # Check your subscription for correct version

# Access level and language (for trial subscriptions)
SPORTRADAR_ACCESS_LEVEL = "trial"  # Options: "trial", "production"
SPORTRADAR_LANGUAGE = "en"  # Language code

# Debug: Print configuration status
print(f"[SPORTRADAR CONFIG] After loading .env:")
print(f"[SPORTRADAR CONFIG] SPORTRADAR_NBA_API_KEY: {'Set (' + SPORTRADAR_NBA_API_KEY[:10] + '...)' if SPORTRADAR_NBA_API_KEY else 'NOT SET'}")
print(f"[SPORTRADAR CONFIG] SPORTRADAR_SYNERGY_API_KEY: {'Set (' + SPORTRADAR_SYNERGY_API_KEY[:10] + '...)' if SPORTRADAR_SYNERGY_API_KEY else 'NOT SET'}")
print(f"[SPORTRADAR CONFIG] SPORTRADAR_GLOBAL_API_KEY: {'Set (' + SPORTRADAR_GLOBAL_API_KEY[:10] + '...)' if SPORTRADAR_GLOBAL_API_KEY else 'NOT SET'}")

if SPORTRADAR_NBA_API_KEY:
    print(f"[SPORTRADAR CONFIG] ✓ NBA API configured!")
if SPORTRADAR_SYNERGY_API_KEY:
    print(f"[SPORTRADAR CONFIG] ✓ Synergy API configured!")
if SPORTRADAR_GLOBAL_API_KEY:
    print(f"[SPORTRADAR CONFIG] ✓ Global Basketball API configured!")


def get_sportradar_nba_url(endpoint: str, use_us_domain: bool = False, include_access_level: bool = True, use_headers: bool = False) -> str:
    """
    Build Sportradar NBA API URL.
    
    Args:
        endpoint: API endpoint path (e.g., 'schedule', 'standings')
        use_us_domain: If True, use .us domain instead of .com
        include_access_level: If True, include access_level/language in path
        use_headers: If True, don't append API key to URL (will be sent in headers)
    
    Returns:
        Full API URL (with or without API key based on use_headers)
    """
    if not SPORTRADAR_NBA_API_KEY:
        raise ValueError("SPORTRADAR_NBA_API_KEY not configured")
    
    base_url = SPORTRADAR_NBA_BASE_URL_US if use_us_domain else SPORTRADAR_NBA_BASE_URL
    
    # When using headers, always use .com domain with access_level/language
    if use_headers:
        # Format: https://api.sportradar.com/nba/{access_level}/{version}/{language}/{endpoint}
        url = f"{SPORTRADAR_NBA_BASE_URL}/{SPORTRADAR_ACCESS_LEVEL}/{SPORTRADAR_NBA_VERSION}/{SPORTRADAR_LANGUAGE}/{endpoint}"
    elif include_access_level and use_us_domain:
        # Format: https://api.sportradar.us/nba/{access_level}/{version}/{language}/{endpoint}?api_key={key}
        url = f"{base_url}/{SPORTRADAR_ACCESS_LEVEL}/{SPORTRADAR_NBA_VERSION}/{SPORTRADAR_LANGUAGE}/{endpoint}"
        url = f"{url}?api_key={SPORTRADAR_NBA_API_KEY}"
    else:
        # Format: https://api.sportradar.com/nba/{version}/{endpoint}?api_key={key}
        url = f"{base_url}/{SPORTRADAR_NBA_VERSION}/{endpoint}"
        url = f"{url}?api_key={SPORTRADAR_NBA_API_KEY}"
    
    return url


def get_sportradar_synergy_url(endpoint: str) -> str:
    """
    Build Sportradar Synergy Basketball API URL.
    
    Args:
        endpoint: API endpoint path
    
    Returns:
        Full API URL with authentication
    """
    if not SPORTRADAR_SYNERGY_API_KEY:
        raise ValueError("SPORTRADAR_SYNERGY_API_KEY not configured")
    
    url = f"{SPORTRADAR_SYNERGY_BASE_URL}/{SPORTRADAR_SYNERGY_VERSION}/{endpoint}"
    return f"{url}?api_key={SPORTRADAR_SYNERGY_API_KEY}"


def get_sportradar_global_url(endpoint: str) -> str:
    """
    Build Sportradar Global Basketball API URL.
    
    Args:
        endpoint: API endpoint path
    
    Returns:
        Full API URL with authentication
    """
    if not SPORTRADAR_GLOBAL_API_KEY:
        raise ValueError("SPORTRADAR_GLOBAL_API_KEY not configured")
    
    url = f"{SPORTRADAR_GLOBAL_BASE_URL}/{SPORTRADAR_GLOBAL_VERSION}/{endpoint}"
    return f"{url}?api_key={SPORTRADAR_GLOBAL_API_KEY}"


def fetch_sportradar_nba(endpoint: str, params: Optional[dict] = None, use_us_domain: bool = False, include_access_level: bool = True, use_headers: bool = False) -> dict:
    """
    Fetch data from Sportradar NBA API.
    
    Args:
        endpoint: API endpoint path
        params: Optional query parameters
        use_us_domain: If True, use .us domain instead of .com
        include_access_level: If True, include access_level/language in path
        use_headers: If True, use header-based authentication (x-api-key header) instead of query parameter
    
    Returns:
        JSON response as dictionary
    """
    import requests
    
    url = get_sportradar_nba_url(endpoint, use_us_domain=use_us_domain, include_access_level=include_access_level, use_headers=use_headers)
    
    if params:
        # Add params to URL
        param_str = "&".join([f"{k}={v}" for k, v in params.items()])
        if "?" in url:
            url = f"{url}&{param_str}"
        else:
            url = f"{url}?{param_str}"
    
    print(f"[SPORTRADAR] Fetching URL: {url[:100]}...")  # Debug: show URL being called
    
    # Prepare headers
    headers = {}
    if use_headers:
        headers = {
            "accept": "application/json",
            "x-api-key": SPORTRADAR_NBA_API_KEY
        }
    
    # #region agent log
    try:
        from pathlib import Path
        import json
        debug_log_path = Path(__file__).parent.parent.parent / '.cursor' / 'debug.log'
        log_entry = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "URL",
            "location": "sportradar_config.py:fetch_sportradar_nba",
            "message": "Before API request",
            "data": {"url": url, "endpoint": endpoint, "has_params": params is not None, "use_headers": use_headers},
            "timestamp": int(__import__('datetime').datetime.now(__import__('datetime').UTC).timestamp() * 1000)
        }
        with open(debug_log_path, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception:
        pass
    # #endregion
    
    response = requests.get(url, headers=headers, timeout=30)
    
    # #region agent log
    try:
        log_entry = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "URL",
            "location": "sportradar_config.py:fetch_sportradar_nba",
            "message": "After API request",
            "data": {"status_code": response.status_code, "url": url, "response_length": len(response.text)},
            "timestamp": int(__import__('datetime').datetime.now(__import__('datetime').UTC).timestamp() * 1000)
        }
        with open(debug_log_path, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception:
        pass
    # #endregion
    
    # Better error handling - show response details
    if response.status_code != 200:
        print(f"[SPORTRADAR] Error response status: {response.status_code}")
        print(f"[SPORTRADAR] Error response text: {response.text[:500]}")
        
        # #region agent log
        try:
            log_entry = {
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "URL",
                "location": "sportradar_config.py:fetch_sportradar_nba",
                "message": "Error response received",
                "data": {"status_code": response.status_code, "response_text": response.text[:500], "headers": dict(response.headers)},
                "timestamp": int(__import__('datetime').datetime.now(__import__('datetime').UTC).timestamp() * 1000)
            }
            with open(debug_log_path, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception:
            pass
        # #endregion
        
        response.raise_for_status()
    
    # #region agent log
    try:
        response_json = response.json()
        log_entry = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "RESPONSE",
            "location": "sportradar_config.py:fetch_sportradar_nba",
            "message": "Successful response received",
            "data": {"status_code": response.status_code, "response_keys": list(response_json.keys()) if isinstance(response_json, dict) else "not_dict", "response_type": type(response_json).__name__, "response_preview": str(response_json)[:500]},
            "timestamp": int(__import__('datetime').datetime.now(__import__('datetime').UTC).timestamp() * 1000)
        }
        with open(debug_log_path, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception:
        pass
    # #endregion
    
    return response.json()


def fetch_sportradar_synergy(endpoint: str, params: Optional[dict] = None) -> dict:
    """
    Fetch data from Sportradar Synergy Basketball API.
    
    Args:
        endpoint: API endpoint path
        params: Optional query parameters
    
    Returns:
        JSON response as dictionary
    """
    import requests
    
    url = get_sportradar_synergy_url(endpoint)
    
    if params:
        param_str = "&".join([f"{k}={v}" for k, v in params.items()])
        url = f"{url}&{param_str}"
    
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_sportradar_global(endpoint: str, params: Optional[dict] = None) -> dict:
    """
    Fetch data from Sportradar Global Basketball API.
    
    Args:
        endpoint: API endpoint path
        params: Optional query parameters
    
    Returns:
        JSON response as dictionary
    """
    import requests
    
    url = get_sportradar_global_url(endpoint)
    
    if params:
        param_str = "&".join([f"{k}={v}" for k, v in params.items()])
        url = f"{url}&{param_str}"
    
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def is_sportradar_configured() -> bool:
    """
    Check if at least one Sportradar API is configured.
    
    Returns:
        True if at least one API key is set, False otherwise
    """
    return bool(SPORTRADAR_NBA_API_KEY or SPORTRADAR_SYNERGY_API_KEY or SPORTRADAR_GLOBAL_API_KEY)

