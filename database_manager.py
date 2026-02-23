# database_manager.py - Complete database operations for Kirana-Predict

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from database_connection import get_supabase_client

class KiranaDatabase:
    """
    Universal database manager for Kirana-Predict
    Handles: API sync, Watchdog sync, Manual entry
    """
    
    def __init__(self):
        """Initialize database connection"""
        self.supabase = get_supabase_client()
    
    # ========================================
    # SALES OPERATIONS
    # ========================================
    
    def add_sale(self, sale_data: Dict[str, Any], source: str = 'manual') -> Dict:
        """Add a single sale transaction"""
        sale_data['data_source'] = source
        sale_data['created_at'] = datetime.now().isoformat()
        
        if 'transaction_id' not in sale_data:
            sale_data['transaction_id'] = f"TXN_{int(datetime.now().timestamp())}"
        
        try:
            response = self.supabase.table('sales').insert(sale_data).execute()
            print(f"✅ Sale added: {sale_data.get('product_name', 'Unknown')}")
            return response.data[0] if response.data else {}
        except Exception as e:
            print(f"❌ Error adding sale: {e}")
            raise
    
    def get_all_sales(self) -> pd.DataFrame:
        """Get all sales data"""
        try:
            response = self.supabase.table('sales').select("*").execute()
            df = pd.DataFrame(response.data)
            
            if not df.empty:
                df['transaction_date'] = pd.to_datetime(df['transaction_date'])
            
            print(f"📊 Loaded {len(df)} sales records")
            return df
        except Exception as e:
            print(f"❌ Error loading sales: {e}")
            return pd.DataFrame()
    
    def get_recent_sales(self, days: int = 7) -> pd.DataFrame:
        """Get sales from last N days"""
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        try:
            response = self.supabase.table('sales')\
                .select("*")\
                .gte('transaction_date', start_date)\
                .order('transaction_date', desc=True)\
                .execute()
            
            df = pd.DataFrame(response.data)
            if not df.empty:
                df['transaction_date'] = pd.to_datetime(df['transaction_date'])
            
            return df
        except Exception as e:
            print(f"❌ Error loading recent sales: {e}")
            return pd.DataFrame()
    
    def get_all_products(self) -> pd.DataFrame:
        """Get all products"""
        try:
            response = self.supabase.table('products').select("*").execute()
            return pd.DataFrame(response.data)
        except Exception as e:
            print(f"❌ Error loading products: {e}")
            return pd.DataFrame()


# ========================================
# CONVENIENCE FUNCTIONS (Backward Compatible)
# ========================================

def load_data() -> pd.DataFrame:
    """
    Backward compatible function
    Replaces old CSV-based load_data()
    """
    db = KiranaDatabase()
    return db.get_all_sales()

def load_data_from_db() -> pd.DataFrame:
    """Explicit database loader"""
    db = KiranaDatabase()
    return db.get_all_sales()


# ========================================
# TESTING
# ========================================

if __name__ == "__main__":
    print("🔄 Testing Database Manager...\n")
    
    try:
        db = KiranaDatabase()
        
        # Test: Load sales
        print("=" * 60)
        print("TEST: Loading Sales")
        print("=" * 60)
        sales = db.get_all_sales()
        print(f"✅ Loaded {len(sales)} sales\n")
        
        print("🎉 Test Passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
