"""
Supabase Cache Module
Handles caching of bulk API data in Supabase for persistent storage.
"""

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import pandas as pd

from supabase_config import get_supabase_client, is_supabase_configured

logger = logging.getLogger(__name__)


def get_cached_bulk_data(
    data_type: str,
    season: str,
    ttl_hours: int = 1,
    **kwargs
) -> Optional[Any]:
    """
    Get cached bulk API data from Supabase.
    
    Args:
        data_type: Type of data ('synergy', 'game_logs', 'advanced_stats', 'drives_stats', etc.)
        season: Season string (e.g., '2025-26')
        ttl_hours: Time-to-live in hours (default: 1)
        **kwargs: Additional parameters to include in cache key (e.g., last_n_games=5, measure_type='Advanced')
    
    Returns:
        Cached data (dict for synergy, DataFrame for others), or None if cache miss or error
    """
    if not is_supabase_configured():
        logger.debug("Supabase not configured, skipping cache lookup")
        print("[CACHE] Supabase not configured, skipping cache lookup")
        return None
    
    # Build cache key with optional parameters
    cache_key_parts = [data_type]
    if kwargs:
        # Sort kwargs for consistent cache keys
        sorted_kwargs = sorted(kwargs.items())
        for key, value in sorted_kwargs:
            if value is not None:
                cache_key_parts.append(f"{key}_{value}")
    cache_key_parts.append(season)
    cache_key = "_".join(cache_key_parts)
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            print(f"[CACHE] Failed to get Supabase client for {cache_key}")
            print(f"[CACHE] This means Supabase is not configured or client creation failed")
            return None
        
        # Query cache
        print(f"[CACHE] Querying cache for key: {cache_key}")
        try:
            result = supabase.table('cached_api_data').select('*').eq('cache_key', cache_key).execute()
        except Exception as query_error:
            print(f"[CACHE ERROR] Failed to query cache table: {query_error}")
            print(f"[CACHE ERROR] This might mean the table doesn't exist or there's a permissions issue")
            import traceback
            traceback.print_exc()
            return None
        
        if not result.data or len(result.data) == 0:
            logger.debug(f"Cache miss for {cache_key}")
            print(f"[CACHE MISS] {cache_key}")
            return None
        
        cache_entry = result.data[0]
        print(f"[CACHE HIT] {cache_key}")
        
        # Check expiration
        expires_at_str = cache_entry['expires_at']
        print(f"[CACHE] Checking expiration for {cache_key}, expires_at: {expires_at_str}")
        try:
            # Handle timezone-aware and timezone-naive timestamps
            if 'Z' in expires_at_str or '+' in expires_at_str or expires_at_str.count('-') > 2:
                # Timezone-aware
                expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
                now = datetime.now(expires_at.tzinfo)
            else:
                # Timezone-naive - assume UTC
                expires_at = datetime.fromisoformat(expires_at_str.replace('Z', ''))
                from datetime import timezone
                expires_at = expires_at.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
            print(f"[CACHE] Now: {now}, Expires: {expires_at}, Expired: {now > expires_at}")
            if now > expires_at:
                logger.debug(f"Cache expired for {cache_key}")
                print(f"[CACHE] Cache expired for {cache_key}, deleting entry")
                # Delete expired entry
                try:
                    supabase.table('cached_api_data').delete().eq('cache_key', cache_key).execute()
                except Exception as e:
                    logger.warning(f"Failed to delete expired cache entry: {e}")
                return None
        except Exception as exp_error:
            print(f"[CACHE ERROR] Failed to parse expiration date: {exp_error}")
            print(f"[CACHE ERROR] expires_at value: {expires_at_str}")
            import traceback
            traceback.print_exc()
            # Continue anyway - don't fail on expiration parsing
        
        # Parse data based on type
        data_json = cache_entry['data']
        print(f"[CACHE] Parsing cached data for {cache_key}")
        print(f"[CACHE] Data type: {type(data_json)}")
        print(f"[CACHE] Data is None: {data_json is None}")
        print(f"[CACHE] Data is empty: {not data_json if data_json else 'N/A'}")
        if data_json:
            print(f"[CACHE] Data sample (first 500 chars): {str(data_json)[:500]}")
        
        try:
            # Check if it's synergy data (dict of DataFrames or nested dict)
            is_synergy_data = (
                data_type == 'synergy' or 
                data_type == 'all_team_synergy' or
                (isinstance(data_json, dict) and any(
                    isinstance(v, (dict, list)) or 
                    (isinstance(v, dict) and any(isinstance(sub_v, (dict, list)) for sub_v in v.values()))
                    for v in data_json.values()
                ))
            )
            if is_synergy_data:
                # Synergy data is a dict of DataFrames (or nested dict)
                result_dict = {}
                if isinstance(data_json, str):
                    # If it's a JSON string, parse it first
                    import json
                    print(f"[CACHE] Parsing synergy JSON string")
                    data_json = json.loads(data_json)
                
                if not isinstance(data_json, dict):
                    print(f"[CACHE ERROR] Expected dict for synergy data, got {type(data_json)}")
                    return None
                
                for key, value in data_json.items():
                    if isinstance(value, list):
                        # Single level dict: {playtype: list_of_records}
                        result_dict[key] = pd.DataFrame(value)
                    elif isinstance(value, dict):
                        # Nested dict: {playtype: {type_grouping: list_of_records}}
                        result_dict[key] = {}
                        for sub_key, sub_value in value.items():
                            if isinstance(sub_value, list):
                                result_dict[key][sub_key] = pd.DataFrame(sub_value)
                            elif isinstance(sub_value, str):
                                # Handle JSON string
                                result_dict[key][sub_key] = pd.read_json(sub_value, orient='records')
                            else:
                                result_dict[key][sub_key] = pd.DataFrame(sub_value) if sub_value else pd.DataFrame()
                    elif isinstance(value, str):
                        # Handle JSON string
                        result_dict[key] = pd.read_json(value, orient='records')
                    else:
                        result_dict[key] = pd.DataFrame(value) if value else pd.DataFrame()
                
                print(f"[CACHE] Successfully parsed synergy data for {cache_key}, {len(result_dict)} top-level keys")
                return result_dict
            else:
                # Other types are single DataFrames
                # Supabase JSONB returns data as Python objects (list/dict), not JSON strings
                # Handle both JSON string (if somehow still a string) and already-parsed list/dict
                
                # First, check if it's already a list (most common case from JSONB)
                if isinstance(data_json, list):
                    print(f"[CACHE] Data is list, converting to DataFrame for {cache_key}, length: {len(data_json)}")
                    if len(data_json) == 0:
                        print(f"[CACHE WARNING] Empty list for {cache_key} - returning empty DataFrame")
                        return pd.DataFrame()
                    try:
                        df = pd.DataFrame(data_json)
                        
                        # Convert date columns back to Timestamps if they were stored as strings
                        # Common date column names in NBA data
                        date_columns = ['GAME_DATE', 'DATE', 'game_date', 'date', 'created_at', 'updated_at']
                        for col in df.columns:
                            if col in date_columns or 'date' in col.lower() or 'time' in col.lower():
                                if df[col].dtype == 'object':
                                    # Try to convert string dates back to Timestamps
                                    try:
                                        df[col] = pd.to_datetime(df[col], errors='coerce')
                                        print(f"[CACHE] Converted date column '{col}' back to Timestamp")
                                    except Exception as date_error:
                                        print(f"[CACHE] Could not convert '{col}' to date: {date_error}")
                        
                        print(f"[CACHE] Successfully converted list to DataFrame for {cache_key}, shape: {df.shape}")
                        return df
                    except Exception as list_error:
                        print(f"[CACHE ERROR] Failed to convert list to DataFrame: {list_error}")
                        print(f"[CACHE ERROR] First item type: {type(data_json[0]) if data_json else 'N/A'}")
                        raise
                
                # Check if it's a dict (single record or nested structure)
                elif isinstance(data_json, dict):
                    print(f"[CACHE] Data is dict, converting to DataFrame for {cache_key}")
                    print(f"[CACHE] Dict keys: {list(data_json.keys())[:10]}")
                    # Check if it's a single record dict or nested
                    try:
                        # Try as list of one record first
                        df = pd.DataFrame([data_json])
                        print(f"[CACHE] Successfully converted dict to DataFrame (single record), shape: {df.shape}")
                        return df
                    except Exception as dict_error:
                        print(f"[CACHE ERROR] Failed to convert dict as single record: {dict_error}")
                        # Might be nested structure - try direct conversion
                        try:
                            df = pd.DataFrame(data_json)
                            print(f"[CACHE] Successfully converted dict directly, shape: {df.shape}")
                            return df
                        except Exception as e2:
                            print(f"[CACHE ERROR] Also failed direct dict conversion: {e2}")
                            raise dict_error
                
                # Check if it's a JSON string (less common with JSONB)
                elif isinstance(data_json, str):
                    print(f"[CACHE] Data is JSON string, parsing for {cache_key}, length: {len(data_json)}")
                    if len(data_json) == 0:
                        print(f"[CACHE ERROR] Empty JSON string for {cache_key}")
                        return None
                    try:
                        df = pd.read_json(data_json, orient='records')
                        print(f"[CACHE] Successfully parsed JSON string, shape: {df.shape}")
                        return df
                    except Exception as json_error:
                        print(f"[CACHE ERROR] Failed to parse JSON string: {json_error}")
                        # Try json.loads first, then DataFrame
                        try:
                            import json
                            parsed = json.loads(data_json)
                            df = pd.DataFrame(parsed) if isinstance(parsed, list) else pd.DataFrame([parsed])
                            print(f"[CACHE] Successfully parsed via json.loads, shape: {df.shape}")
                            return df
                        except Exception as e2:
                            print(f"[CACHE ERROR] Also failed json.loads approach: {e2}")
                            raise json_error
                else:
                    print(f"[CACHE ERROR] Unexpected data type: {type(data_json)}")
                    print(f"[CACHE ERROR] Data value sample: {str(data_json)[:500]}")
                    return None
        except Exception as parse_error:
            print(f"[CACHE ERROR] Failed to parse cached data for {cache_key}: {parse_error}")
            print(f"[CACHE ERROR] Data type: {type(data_json)}")
            if data_json:
                print(f"[CACHE ERROR] Data sample: {str(data_json)[:500]}")
            import traceback
            traceback.print_exc()
            return None
    
    except Exception as e:
        logger.error(f"Error retrieving cache for {cache_key}: {e}")
        print(f"[CACHE ERROR] Error retrieving cache for {cache_key}: {e}")
        import traceback
        traceback.print_exc()
        return None


def set_cached_bulk_data(
    data_type: str,
    season: str,
    data: Any,
    ttl_hours: int = 1,
    **kwargs
) -> bool:
    """
    Store bulk API data in Supabase cache.
    
    Args:
        data_type: Type of data ('synergy', 'game_logs', 'advanced_stats', 'drives_stats', etc.)
        season: Season string (e.g., '2025-26')
        data: Data to cache (dict for synergy, DataFrame for others)
        ttl_hours: Time-to-live in hours (default: 1)
        **kwargs: Additional parameters to include in cache key (e.g., last_n_games=5, measure_type='Advanced')
    
    Returns:
        True if successful, False otherwise
    """
    if not is_supabase_configured():
        logger.debug("Supabase not configured, skipping cache storage")
        print("[CACHE] Supabase not configured, skipping cache storage")
        return False
    
    # Build cache key with optional parameters (same logic as get_cached_bulk_data)
    cache_key_parts = [data_type]
    if kwargs:
        sorted_kwargs = sorted(kwargs.items())
        for key, value in sorted_kwargs:
            if value is not None:
                cache_key_parts.append(f"{key}_{value}")
    cache_key_parts.append(season)
    cache_key = "_".join(cache_key_parts)
    # Ensure expires_at is timezone-aware (UTC)
    from datetime import timezone
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            return False
        
        # Serialize data based on type
        # Supabase JSONB accepts Python objects (dict/list) directly - no need for JSON strings
        # The client will automatically serialize Python objects to JSONB
        print(f"[CACHE] Serializing data for {cache_key}, data type: {type(data)}")
        # Check if it's synergy data (dict of DataFrames or nested dict)
        is_synergy_data = (
            data_type == 'synergy' or 
            data_type == 'all_team_synergy' or
            (isinstance(data, dict) and any(
                isinstance(v, pd.DataFrame) or 
                (isinstance(v, dict) and any(isinstance(sub_v, pd.DataFrame) for sub_v in v.values()))
                for v in data.values()
            ))
        )
        if is_synergy_data:
            # Synergy data is a dict of DataFrames (or nested dict)
            data_json = {}
            for key, value in data.items():
                if isinstance(value, pd.DataFrame):
                    # Single level dict: {playtype: df}
                    df_clean = value.copy()
                    # Convert Timestamp columns to strings
                    for col in df_clean.select_dtypes(include=['datetime64']).columns:
                        df_clean[col] = df_clean[col].astype(str)
                    # Replace NaN with None (JSON-compliant)
                    df_clean = df_clean.where(pd.notnull(df_clean), None)
                    data_json[key] = df_clean.to_dict(orient='records')
                    # Final pass: replace any NaN that might have slipped through
                    import math
                    data_json[key] = [
                        {k: (None if (isinstance(v, float) and math.isnan(v)) else v) for k, v in record.items()}
                        for record in data_json[key]
                    ]
                elif isinstance(value, dict):
                    # Nested dict: {playtype: {type_grouping: df}}
                    data_json[key] = {}
                    for sub_key, df in value.items():
                        if isinstance(df, pd.DataFrame):
                            df_clean = df.copy()
                            # Convert Timestamp columns to strings
                            for col in df_clean.select_dtypes(include=['datetime64']).columns:
                                df_clean[col] = df_clean[col].astype(str)
                            # Replace NaN with None (JSON-compliant)
                            df_clean = df_clean.where(pd.notnull(df_clean), None)
                            data_json[key][sub_key] = df_clean.to_dict(orient='records')
                            # Final pass: replace any NaN that might have slipped through
                            import math
                            data_json[key][sub_key] = [
                                {k: (None if (isinstance(v, float) and math.isnan(v)) else v) for k, v in record.items()}
                                for record in data_json[key][sub_key]
                            ]
                        else:
                            data_json[key][sub_key] = df
                else:
                    data_json[key] = value
            print(f"[CACHE] Serialized synergy data: {len(data_json)} top-level keys")
        else:
            # Other types are DataFrames
            if isinstance(data, pd.DataFrame):
                # Convert DataFrame to list of dicts (Python objects)
                # Supabase JSONB will handle this automatically
                print(f"[CACHE] Serializing DataFrame with shape: {data.shape}")
                if len(data) > 100000:
                    print(f"[CACHE] Large DataFrame detected ({len(data)} rows)")
                
                # Create a copy to avoid modifying the original
                df_clean = data.copy()
                
                # Convert Timestamp/datetime columns to strings
                # First, handle explicit datetime64 dtypes
                datetime_cols = df_clean.select_dtypes(include=['datetime64']).columns
                for col in datetime_cols:
                    print(f"[CACHE] Converting datetime64 column '{col}' to string")
                    df_clean[col] = df_clean[col].astype(str)
                
                # Then, check object columns for Timestamp objects
                object_cols = df_clean.select_dtypes(include=['object']).columns
                for col in object_cols:
                    # Check first non-null value to see if it's a Timestamp
                    non_null_vals = df_clean[col].dropna()
                    if len(non_null_vals) > 0:
                        sample_val = non_null_vals.iloc[0]
                        if isinstance(sample_val, pd.Timestamp):
                            print(f"[CACHE] Converting Timestamp column '{col}' to string")
                            df_clean[col] = df_clean[col].astype(str)
                
                # Replace NaN/NaT with None (JSON-compliant)
                # This handles both float NaN and datetime NaT
                # Use where() to replace NaN/NaT with None
                df_clean = df_clean.where(pd.notnull(df_clean), None)
                
                # Convert to dict - this will convert any remaining NaN to None
                data_json = df_clean.to_dict(orient='records')
                # Final pass: replace any NaN/Inf that might have slipped through
                import math
                data_json = [
                    {
                        k: (
                            None if (
                                (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) or
                                (v is pd.NA) or
                                (isinstance(v, str) and v.lower() in ['nan', 'none', ''])
                            ) else v
                        )
                        for k, v in record.items()
                    }
                    for record in data_json
                ]
                print(f"[CACHE] Serialized DataFrame to list of dicts, length: {len(data_json)} records")
            else:
                logger.error(f"Unexpected data type for {data_type}: {type(data)}")
                return False
        
        # Upsert cache entry
        cache_entry = {
            'cache_key': cache_key,
            'data_type': data_type,
            'season': season,
            'data': data_json,
            'expires_at': expires_at.isoformat()
        }
        
        print(f"[CACHE] Attempting to store cache entry for {cache_key}")
        try:
            # For large data, use a longer timeout
            if isinstance(data_json, str) and len(data_json) > 1000000:  # > 1MB
                print(f"[CACHE] Large data detected ({len(data_json)} chars), using extended timeout")
                # Note: Supabase client doesn't support custom timeouts directly
                # We'll need to handle this differently or chunk the data
                response = supabase.table('cached_api_data').upsert(
                    cache_entry,
                    on_conflict='cache_key'
                ).execute()
            else:
                response = supabase.table('cached_api_data').upsert(
                    cache_entry,
                    on_conflict='cache_key'
                ).execute()
            
            logger.debug(f"Cached {cache_key} (expires: {expires_at})")
            print(f"[CACHE SET] {cache_key} (expires: {expires_at})")
            return True
        except Exception as upsert_error:
            # Check if it's a timeout error
            if 'timeout' in str(upsert_error).lower() or '57014' in str(upsert_error):
                print(f"[CACHE WARNING] Timeout storing {cache_key} - data may be too large")
                print(f"[CACHE WARNING] Consider chunking large DataFrames or increasing database timeout")
            raise  # Re-raise to be caught by outer exception handler
    
    except Exception as e:
        logger.error(f"Error storing cache for {cache_key}: {e}")
        print(f"[CACHE ERROR] Error storing cache for {cache_key}: {e}")
        import traceback
        traceback.print_exc()
        return False


def clear_expired_cache() -> int:
    """
    Clear expired cache entries from Supabase.
    
    Returns:
        Number of entries deleted
    """
    if not is_supabase_configured():
        return 0
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            return 0
        
        now = datetime.now().isoformat()
        
        # Delete expired entries
        result = supabase.table('cached_api_data').delete().lt('expires_at', now).execute()
        
        deleted_count = len(result.data) if result.data else 0
        logger.info(f"Cleared {deleted_count} expired cache entries")
        return deleted_count
    
    except Exception as e:
        logger.error(f"Error clearing expired cache: {e}")
        return 0

