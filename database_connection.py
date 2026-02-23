import os
import sys
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from supabase import create_client, Client


class SupabaseConnection:
    """
    Manages Supabase database connection with proper error handling.
    
    Features:
    - Validates credentials before connecting
    - Provides detailed error messages
    - Reusable across the application
    - Supports multiple environments (dev/prod)
    """
    
    def __init__(self, env_file: str = ".env"):
        """
        Initialize Supabase connection.
        
        Args:
            env_file: Path to environment file (default: .env)
        """
        self.env_file = env_file
        self.client: Optional[Client] = None
        self._load_credentials()
    
    def _load_credentials(self) -> None:
        """Load and validate Supabase credentials from environment."""
        # Load environment variables
        load_dotenv(self.env_file)
        
        # Get credentials
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        
        # Validate credentials exist
        if not self.url or not self.key:
            self._print_error("Missing credentials in .env file")
            self._print_setup_instructions()
            sys.exit(1)
        
        # Validate URL format
        if not self.url.startswith("https://"):
            self._print_error(f"Invalid SUPABASE_URL format: {self.url}")
            self._print_setup_instructions()
            sys.exit(1)
        
        print("✅ Credentials loaded successfully")
    
    def connect(self) -> Client:
        """
        Create and return Supabase client.
        
        Returns:
            Supabase client instance
        
        Raises:
            ConnectionError: If connection fails
        """
        try:
            self.client = create_client(self.url, self.key)
            print(f"✅ Connected to Supabase: {self._mask_url(self.url)}")
            return self.client
        except Exception as e:
            self._print_error(f"Failed to create client: {str(e)}")
            raise ConnectionError(f"Supabase connection failed: {e}")
    
    def test_connection(self, table_name: str = "sales") -> bool:
        """
        Test database connection by querying a table.
        
        Args:
            table_name: Name of table to test (default: sales)
        
        Returns:
            True if connection successful, False otherwise
        """
        if not self.client:
            print("⚠️  Client not initialized. Connecting...")
            self.connect()
        
        try:
            # Try to fetch one row from the table
            response = self.client.table(table_name).select("*").limit(1).execute()
            
            # Check if query was successful
            if hasattr(response, 'data'):
                row_count = len(response.data) if response.data else 0
                print(f"✅ SUCCESS: Connected to Supabase!")
                print(f"📊 Table '{table_name}' is accessible ({row_count} row(s) found)")
                return True
            else:
                print(f"⚠️  Warning: Unexpected response format")
                return False
                
        except Exception as e:
            self._handle_connection_error(e, table_name)
            return False
    
    def get_client(self) -> Client:
        """
        Get the Supabase client instance.
        Creates connection if not already established.
        
        Returns:
            Supabase client
        """
        if not self.client:
            self.connect()
        return self.client
    
    def _handle_connection_error(self, error: Exception, table_name: str) -> None:
        """Handle and display detailed error information."""
        error_str = str(error).lower()
        
        print(f"\n❌ CONNECTION ERROR: {error}\n")
        
        # Provide specific troubleshooting based on error type
        if "relation" in error_str and "does not exist" in error_str:
            print(f"🔍 Table '{table_name}' does not exist in database")
            print("\n💡 Solutions:")
            print("   1. Check if you ran the database schema SQL")
            print("   2. Verify table name spelling")
            print("   3. Go to Supabase Dashboard → Table Editor to see available tables")
        
        elif "invalid api key" in error_str or "jwt" in error_str:
            print("🔑 Invalid or expired API key")
            print("\n💡 Solutions:")
            print("   1. Go to Supabase Dashboard → Settings → API")
            print("   2. Copy the 'anon public' key (not service_role)")
            print("   3. Update SUPABASE_KEY in your .env file")
        
        elif "could not resolve host" in error_str or "connection refused" in error_str:
            print("🌐 Network connection issue")
            print("\n💡 Solutions:")
            print("   1. Check your internet connection")
            print("   2. Verify SUPABASE_URL is correct")
            print("   3. Check if firewall is blocking connection")
        
        elif "database" in error_str and "not found" in error_str:
            print("🗄️  Database or project not found")
            print("\n💡 Solutions:")
            print("   1. Verify your Supabase project is active")
            print("   2. Check project URL in Supabase Dashboard")
            print("   3. Ensure project hasn't been paused/deleted")
        
        else:
            print("💡 General troubleshooting:")
            print("   1. Check .env file exists and has correct values")
            print("   2. Verify Supabase project is active (not paused)")
            print("   3. Check API key hasn't expired")
            print("   4. Ensure you're using 'anon public' key, not 'service_role'")
    
    def _print_error(self, message: str) -> None:
        """Print formatted error message."""
        print(f"\n{'='*60}")
        print(f"❌ ERROR: {message}")
        print(f"{'='*60}\n")
    
    def _print_setup_instructions(self) -> None:
        """Print setup instructions for .env file."""
        print("📝 Your .env file should look like this:\n")
        print("SUPABASE_URL=https://xxxxx.supabase.co")
        print("SUPABASE_KEY=your_anon_key_here\n")
        print("Get these values from:")
        print("Supabase Dashboard → Settings → API\n")
    
    def _mask_url(self, url: str) -> str:
        """Mask URL for security when printing."""
        if not url:
            return "None"
        # Show only first 30 chars and last 10 chars
        if len(url) > 40:
            return f"{url[:30]}...{url[-10:]}"
        return url
    
    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get connection information (for debugging).
        
        Returns:
            Dictionary with connection details
        """
        return {
            "url": self._mask_url(self.url),
            "key_length": len(self.key) if self.key else 0,
            "connected": self.client is not None,
            "env_file": self.env_file
        }


# ============================================
# MODULE-LEVEL CONVENIENCE FUNCTIONS
# ============================================

# Global instance (lazy initialization)
_db_connection: Optional[SupabaseConnection] = None

def get_supabase_client() -> Client:
    """
    Get Supabase client (creates connection if needed).
    Use this in your app.py and other modules.
    
    Returns:
        Supabase client instance
    
    Example:
        supabase = get_supabase_client()
        data = supabase.table('sales').select('*').execute()
    """
    global _db_connection
    if _db_connection is None:
        _db_connection = SupabaseConnection()
    return _db_connection.get_client()

def test_database_connection(table_name: str = "sales") -> bool:
    """
    Quick connection test function.
    
    Args:
        table_name: Table to test (default: sales)
    
    Returns:
        True if successful
    """
    global _db_connection
    if _db_connection is None:
        _db_connection = SupabaseConnection()
    return _db_connection.test_connection(table_name)


# ============================================
# MAIN: Run tests when file is executed directly
# ============================================

if __name__ == "__main__":
    print("🔄 Starting Supabase Connection Test...\n")
    
    # Test 1: Initialize connection
    print("=" * 60)
    print("TEST 1: Loading Credentials")
    print("=" * 60)
    try:
        db = SupabaseConnection()
        print("✅ Test 1 Passed\n")
    except SystemExit:
        print("❌ Test 1 Failed - Fix credentials and try again\n")
        sys.exit(1)
    
    # Test 2: Connect to Supabase
    print("=" * 60)
    print("TEST 2: Establishing Connection")
    print("=" * 60)
    try:
        client = db.connect()
        print("✅ Test 2 Passed\n")
    except Exception as e:
        print(f"❌ Test 2 Failed: {e}\n")
        sys.exit(1)
    
    # Test 3: Query database
    print("=" * 60)
    print("TEST 3: Testing Database Query")
    print("=" * 60)
    success = db.test_connection("sales")
    if success:
        print("✅ Test 3 Passed\n")
    else:
        print("❌ Test 3 Failed\n")
        sys.exit(1)
    
    # Test 4: Show connection info
    print("=" * 60)
    print("TEST 4: Connection Information")
    print("=" * 60)
    info = db.get_connection_info()
    for key, value in info.items():
        print(f"   {key}: {value}")
    print("✅ Test 4 Passed\n")
    
    # All tests passed
    print("=" * 60)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 60)
    print("\n✅ Your database connection is working perfectly!")
    print("✅ You can now use this in your app.py")
    print("\n📝 Usage in other files:")
    print("   from database_connection import get_supabase_client")
    print("   supabase = get_supabase_client()")
    print("   data = supabase.table('sales').select('*').execute()")