#!/usr/bin/env python3
"""
Fetch DraftKings Draftables
Fetches player draftables data from DraftKings API and extracts displayName, salary, and position.
"""

import requests
import pandas as pd
import json
import os
import sys
from typing import Optional, Dict, List
from urllib.parse import quote
from datetime import datetime

# Configuration
DRAFTGROUP_ID = 140610  # Easily changeable
BASE_URL = "https://api.draftkings.com/draftgroups/v1/draftgroups"


def get_headers() -> Dict[str, str]:
    """Return headers matching the cURL request"""
    return {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.5',
        'origin': 'https://www.draftkings.com',
        'priority': 'u=1, i',
        'referer': 'https://www.draftkings.com/',
        'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Brave";v="144"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'sec-gpc': '1',
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Mobile Safari/537.36'
    }


def fetch_direct(draftgroup_id: int) -> Optional[Dict]:
    """
    Attempt direct API call to DraftKings API.
    
    Args:
        draftgroup_id: The draftgroup ID to fetch
        
    Returns:
        JSON response as dict if successful, None otherwise
    """
    url = f"{BASE_URL}/{draftgroup_id}/draftables?format=json"
    headers = get_headers()
    
    try:
        print(f"Attempting direct API call to DraftKings...")
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            print(f"✓ Direct API call successful")
            return response.json()
        elif response.status_code == 403:
            print(f"✗ Direct API call blocked (403 Forbidden)")
            return None
        elif response.status_code == 401:
            print(f"✗ Direct API call unauthorized (401)")
            return None
        elif response.status_code == 404:
            print(f"✗ Draftgroup {draftgroup_id} not found (404)")
            return None
        elif response.status_code == 429:
            print(f"✗ Rate limited (429)")
            return None
        else:
            print(f"✗ Direct API call failed with status {response.status_code}: {response.text[:200]}")
            return None
            
    except requests.exceptions.Timeout:
        print(f"✗ Direct API call timed out")
        return None
    except requests.exceptions.RequestException as e:
        print(f"✗ Direct API call error: {e}")
        return None


def fetch_via_zenrows(draftgroup_id: int) -> Optional[Dict]:
    """
    Fallback to ZenRows proxy if direct call fails.
    
    Args:
        draftgroup_id: The draftgroup ID to fetch
        
    Returns:
        JSON response as dict if successful, None otherwise
    """
    zenrows_api_key = os.getenv('ZENROWS_API_KEY')
    
    if not zenrows_api_key:
        print("✗ ZENROWS_API_KEY environment variable not set, skipping ZenRows fallback")
        return None
    
    url = f"{BASE_URL}/{draftgroup_id}/draftables?format=json"
    encoded_url = quote(url, safe='')
    zenrows_url = f"https://api.zenrows.com/v1/?apikey={zenrows_api_key}&url={encoded_url}"
    
    headers = get_headers()
    
    try:
        print(f"Attempting ZenRows proxy request...")
        response = requests.get(zenrows_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            print(f"✓ ZenRows proxy request successful")
            return response.json()
        else:
            print(f"✗ ZenRows proxy request failed with status {response.status_code}: {response.text[:200]}")
            return None
            
    except requests.exceptions.Timeout:
        print(f"✗ ZenRows proxy request timed out")
        return None
    except requests.exceptions.RequestException as e:
        print(f"✗ ZenRows proxy request error: {e}")
        return None


def extract_player_data(draftables: List[Dict]) -> pd.DataFrame:
    """
    Extract displayName, salary, and position from draftables array.
    
    Args:
        draftables: List of draftable player dictionaries
        
    Returns:
        DataFrame with columns: displayName, salary, position
    """
    players_data = []
    
    for draftable in draftables:
        player_info = {
            'displayName': draftable.get('displayName', ''),
            'salary': draftable.get('salary', None),
            'position': draftable.get('position', '')
        }
        players_data.append(player_info)
    
    df = pd.DataFrame(players_data)
    return df


def main():
    """Main execution function"""
    print(f"=" * 60)
    print(f"DraftKings Draftables Fetcher")
    print(f"Draftgroup ID: {DRAFTGROUP_ID}")
    print(f"=" * 60)
    
    # Try direct fetch first
    data = fetch_direct(DRAFTGROUP_ID)
    
    # If direct fails, try ZenRows fallback
    if data is None:
        print("\nDirect fetch failed, attempting ZenRows fallback...")
        data = fetch_via_zenrows(DRAFTGROUP_ID)
    
    # Check if we got data
    if data is None:
        print("\n✗ Failed to fetch data from both direct API and ZenRows")
        sys.exit(1)
    
    # Extract draftables array
    if 'draftables' not in data:
        print("\n✗ Response does not contain 'draftables' array")
        print(f"Response keys: {list(data.keys())}")
        sys.exit(1)
    
    draftables = data['draftables']
    
    if not isinstance(draftables, list):
        print(f"\n✗ 'draftables' is not a list (type: {type(draftables)})")
        sys.exit(1)
    
    if len(draftables) == 0:
        print("\n✗ 'draftables' array is empty")
        sys.exit(1)
    
    print(f"\n✓ Found {len(draftables)} draftable players")
    
    # Extract player data
    try:
        df = extract_player_data(draftables)
    except Exception as e:
        print(f"\n✗ Error extracting player data: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Remove duplicates based on displayName (keep first occurrence)
    original_count = len(df)
    df = df.drop_duplicates(subset=['displayName'], keep='first')
    duplicates_removed = original_count - len(df)
    
    if duplicates_removed > 0:
        print(f"✓ Removed {duplicates_removed} duplicate player(s) based on displayName")
    
    # Save to CSV
    downloads_path = os.path.expanduser("~/Downloads")
    output_filename = os.path.join(downloads_path, f"draftkings_draftables_{DRAFTGROUP_ID}.csv")
    try:
        df.to_csv(output_filename, index=False)
        print(f"✓ Saved {len(df)} players to {output_filename}")
    except Exception as e:
        print(f"\n✗ Error saving CSV file: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Print summary
    print(f"\n" + "=" * 60)
    print(f"Summary:")
    print(f"  Players fetched: {original_count}")
    print(f"  Duplicates removed: {duplicates_removed}")
    print(f"  Unique players saved: {len(df)}")
    print(f"  Output file: {output_filename}")
    print(f"=" * 60)
    
    # Show first few rows as preview
    if len(df) > 0:
        print(f"\nPreview (first 5 players):")
        print(df.head().to_string(index=False))


if __name__ == '__main__':
    main()
