"""
Supabase Configuration Module
Handles connection to Supabase database and client management.
"""

import os
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv
import logging

# Load environment variables
# Try to load from project root (where .env should be)
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
env_path = project_root / '.env'
print(f"[SUPABASE CONFIG] Loading .env from: {env_path}")
print(f"[SUPABASE CONFIG] .env exists: {env_path.exists()}")
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
else:
    print(f"[SUPABASE CONFIG] .env not found at {env_path}, trying default location")
    load_dotenv()

logger = logging.getLogger(__name__)

# Supabase configuration from environment variables
# Strip whitespace and quotes if present
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().strip('"').strip("'")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip().strip('"').strip("'")  # Anon/public key
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "").strip().strip('"').strip("'")  # Service role key (optional, for migrations)

# Debug: Print configuration status
print(f"[SUPABASE CONFIG] After loading .env:")
print(f"[SUPABASE CONFIG] SUPABASE_URL: {'Set (' + SUPABASE_URL[:30] + '...)' if SUPABASE_URL else 'NOT SET'}")
print(f"[SUPABASE CONFIG] SUPABASE_KEY: {'Set (' + SUPABASE_KEY[:20] + '...)' if SUPABASE_KEY else 'NOT SET'}")
print(f"[SUPABASE CONFIG] SUPABASE_KEY length: {len(SUPABASE_KEY) if SUPABASE_KEY else 0}")

if SUPABASE_URL and SUPABASE_KEY:
    print(f"[SUPABASE CONFIG] ✓ Supabase configured successfully!")
else:
    print("[SUPABASE CONFIG] ✗ WARNING: Supabase not configured!")
    print(f"[SUPABASE CONFIG] Looking for .env at: {env_path}")
    print(f"[SUPABASE CONFIG] .env exists: {env_path.exists()}")
    if env_path.exists():
        print(f"[SUPABASE CONFIG] .env file size: {env_path.stat().st_size} bytes")
        # Try to read first few lines of .env to debug
        try:
            with open(env_path, 'r') as f:
                lines = f.readlines()[:5]
                print(f"[SUPABASE CONFIG] First 5 lines of .env:")
                for i, line in enumerate(lines, 1):
                    # Mask sensitive data
                    masked = line.replace(SUPABASE_KEY, '***MASKED***') if SUPABASE_KEY else line
                    print(f"[SUPABASE CONFIG]   {i}: {masked.strip()}")
        except Exception as e:
            print(f"[SUPABASE CONFIG] Error reading .env: {e}")

# Singleton client instances
_client: Optional[Client] = None
_service_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """
    Get or create the Supabase client instance.
    Uses the anon/public key for regular operations.
    
    Returns:
        Supabase Client instance, or None if configuration is missing
    """
    global _client
    
    if _client is not None:
        return _client
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase credentials not configured. Set SUPABASE_URL and SUPABASE_KEY environment variables.")
        return None
    
    try:
        print(f"[SUPABASE CONFIG] Attempting to create Supabase client...")
        print(f"[SUPABASE CONFIG] URL length: {len(SUPABASE_URL)}, Key length: {len(SUPABASE_KEY)}")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized successfully")
        print(f"[SUPABASE CONFIG] ✓ Supabase client created successfully!")
        return _client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        print(f"[SUPABASE CONFIG] ✗ Failed to create Supabase client: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_supabase_service_client() -> Optional[Client]:
    """
    Get or create the Supabase service client instance.
    Uses the service role key for administrative operations (migrations, etc.).
    
    Returns:
        Supabase Client instance with service role, or None if configuration is missing
    """
    global _service_client
    
    if _service_client is not None:
        return _service_client
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.warning("Supabase service credentials not configured. Set SUPABASE_SERVICE_KEY environment variable.")
        return None
    
    try:
        _service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        logger.info("Supabase service client initialized successfully")
        return _service_client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase service client: {e}")
        return None


def is_supabase_configured() -> bool:
    """
    Check if Supabase is properly configured.
    
    Returns:
        True if both URL and key are set, False otherwise
    """
    return bool(SUPABASE_URL and SUPABASE_KEY)


def reset_clients():
    """
    Reset client instances (useful for testing or reconfiguration).
    """
    global _client, _service_client
    _client = None
    _service_client = None

