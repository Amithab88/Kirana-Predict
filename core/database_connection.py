import os
import sys
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from supabase import create_client, Client

# Try to import streamlit for cloud deployment
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False


class SupabaseConnection:
    """
    Manages Supabase database connection with proper error handling.
    Works on both local (with .env) and Streamlit Cloud (with secrets).
    """
    
    def __init__(self, env_file: str = ".env"):
        """Initialize Supabase connection."""
        self.env_file = env_file
        self.client: Optional[Client] = None
        self._load_credentials()
    
    def _load_credentials(self) -> None:
        """Load and validate Supabase credentials from environment or Streamlit secrets."""
        
        # Try Streamlit secrets first (for cloud deployment)
        if STREAMLIT_AVAILABLE and hasattr(st, 'secrets'):
            try:
                self.url = st.secrets["SUPABASE_URL"]
                self.key = st.secrets["SUPABASE_KEY"]
                print("✅ Credentials loaded from Streamlit secrets")
            except Exception as e:
                print(f"⚠️  Could not load from Streamlit secrets: {e}")
                # Fall back to .env file
                self._load_from_env()
        else:
            # Load from .env file (local development)
            self._load_from_env()
        
        # Validate credentials exist
        if not self.url or not self.key:
            self._print_error("Missing credentials")
            self._print_setup_instructions()
            raise ValueError("Missing Supabase credentials")
        
        # Validate URL format
        if not self.url.startswith("https://"):
            self._print_error(f"Invalid SUPABASE_URL format: {self.url}")
            raise ValueError("Invalid Supabase URL")
        
        print("✅ Credentials validated successfully")
    
    def _load_from_env(self) -> None:
        """Load credentials from .env file."""
        load_dotenv(self.env_file)
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        print("✅ Credentials loaded from .env file")
    
    def connect(self) -> Client:
        """Create and return Supabase client."""
        try:
            self.client = create_client(self.url, self.key)
            print(f"✅ Connected to Supabase: {self._mask_url(self.url)}")
            return self.client
        except Exception as e:
            self._print_error(f"Failed to create client: {str(e)}")
            raise ConnectionError(f"Supabase connection failed: {e}")
    
    def test_connection(self, table_name: str = "sales") -> bool:
        """Test database connection by querying a table."""
        if not self.client:
            print("⚠️  Client not initialized. Connecting...")
            self.connect()
        
        try:
            response = self.client.table(table_name).select("*").limit(1).execute()
            
            if hasattr(response, 'data'):
                row_count = len(response.data) if response.data else 0
                print(f"✅ SUCCESS: Connected to Supabase!")
                print(f"📊 Table '{table_name}' is accessible ({row_count} row(s) found)")
                return True
            else:
                print(f"⚠️  Warning: Unexpected response format")
                return False
                
        except Exception as e:
            print(f"\n❌ CONNECTION ERROR: {error}\n")
            return False
    
    def get_client(self) -> Client:
        """Get the Supabase client instance."""
        if not self.client:
            self.connect()
        return self.client
    
    def _print_error(self, message: str) -> None:
        """Print formatted error message."""
        print(f"\n{'='*60}")
        print(f"❌ ERROR: {message}")
        print(f"{'='*60}\n")
    
    def _print_setup_instructions(self) -> None:
        """Print setup instructions."""
        if STREAMLIT_AVAILABLE:
            print("📝 For Streamlit Cloud:")
            print("   Add secrets in: Settings → Secrets")
            print("   SUPABASE_URL = \"https://xxxxx.supabase.co\"")
            print("   SUPABASE_KEY = \"your_anon_key_here\"\n")
        else:
            print("📝 For local development:")
            print("   Create .env file with:")
            print("   SUPABASE_URL=https://xxxxx.supabase.co")
            print("   SUPABASE_KEY=your_anon_key_here\n")
    
    def _mask_url(self, url: str) -> str:
        """Mask URL for security when printing."""
        if not url:
            return "None"
        if len(url) > 40:
            return f"{url[:30]}...{url[-10:]}"
        return url


# ============================================
# MODULE-LEVEL CONVENIENCE FUNCTIONS
# ============================================

_db_connection: Optional[SupabaseConnection] = None

def get_supabase_client() -> Client:
    """Get Supabase client (creates connection if needed)."""
    global _db_connection
    if _db_connection is None:
        _db_connection = SupabaseConnection()
    return _db_connection.get_client()

def test_database_connection(table_name: str = "sales") -> bool:
    """Quick connection test function."""
    global _db_connection
    if _db_connection is None:
        _db_connection = SupabaseConnection()
    return _db_connection.test_connection(table_name)