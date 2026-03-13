# database_manager.py - Fixed version for Streamlit Cloud

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
        """Get all sales data - FIXED for Streamlit Cloud"""
        try:
            response = self.supabase.table('sales').select("*").execute()
            
            if not response.data:
                print("⚠️  No data returned from Supabase")
                return pd.DataFrame()
            
            df = pd.DataFrame(response.data)
            
            if df.empty:
                print("⚠️  DataFrame is empty")
                return df
            
            # FIX: Handle date conversion with flexible format
            if 'transaction_date' in df.columns:
                try:
                    # Use format='ISO8601' to handle various ISO formats
                    df['transaction_date'] = pd.to_datetime(df['transaction_date'], format='ISO8601')
                except Exception as e:
                    print(f"⚠️  ISO8601 failed, trying mixed format: {e}")
                    # Fallback to mixed format
                    df['transaction_date'] = pd.to_datetime(df['transaction_date'], format='mixed')
            else:
                print(f"⚠️  'transaction_date' column not found. Available columns: {df.columns.tolist()}")
            
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
            if not df.empty and 'transaction_date' in df.columns:
                df['transaction_date'] = pd.to_datetime(df['transaction_date'], format='ISO8601')
            
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
            
    # ============================================
    # STORE MANAGEMENT METHODS (PHASE 3)
    # ============================================
    
    def get_all_stores(self):
        """Get all stores"""
        try:
            response = self.supabase.table('stores').select('*').order('store_code').execute()
            return pd.DataFrame(response.data) if response.data else pd.DataFrame()
        except Exception as e:
           print(f"❌ Error fetching stores: {e}")  # ✅ Changed from st.error
           return pd.DataFrame()
    
    def get_active_stores(self):
        """Get only active stores"""
        try:
            response = (
                self.supabase.table('stores')
                .select('*')
                .eq('is_active', True)
                .order('store_code')
                .execute()
            )
            return pd.DataFrame(response.data) if response.data else pd.DataFrame()
        except Exception as e:
            print(f"❌ Error fetching active stores: {e}")  # ✅ Changed
            return pd.DataFrame()
    
    def get_store_by_code(self, store_code):
        """Get a single store by code"""
        try:
            response = (
                self.supabase.table('stores')
                .select('*')
                .eq('store_code', store_code)
                .execute()
            )
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            print(f"Error fetching store: {e}")
            return None
    
    def add_store(self, store_data):
        """
        Add new store
        store_data = {
            'store_code': 'STORE005',
            'store_name': 'Chennai Store',
            'city': 'Chennai',
            'state': 'Tamil Nadu',
            'address': '...',
            'pos_system': '...',
            'is_active': True
        }
        """
        try:
            response = self.supabase.table('stores').insert(store_data).execute()
            return True
        except Exception as e:
            print(f"Error adding store: {e}")
            return False
    
    def update_store(self, store_code, update_data):
        """Update store details"""
        try:
            response = (
                self.supabase.table('stores')
                .update(update_data)
                .eq('store_code', store_code)
                .execute()
            )
            return True
        except Exception as e:
            print(f"Error updating store: {e}")
            return False
    
    def delete_store(self, store_code):
        """Delete store (soft delete - set inactive)"""
        try:
            response = (
                self.supabase.table('stores')
                .update({'is_active': False})
                .eq('store_code', store_code)
                .execute()
            )
            return True
        except Exception as e:
            print(f"Error deleting store: {e}")
            return False
    
    def get_sales_by_store(self, store_code=None):
        """Get sales filtered by store"""
        try:
            query = self.supabase.table('sales').select('*')
            if store_code:
                query = query.eq('store_code', store_code)
            response = query.execute()
            
            if response.data:
                df = pd.DataFrame(response.data)
                df['transaction_date'] = pd.to_datetime(df['transaction_date'])
                return df
            return pd.DataFrame()
        except Exception as e:
            print(f"Error fetching sales by store: {e}")
            return pd.DataFrame()
    
    def get_store_performance(self):
        """Get performance metrics for all stores"""
        try:
            df = self.get_all_sales()
            if df.empty:
                return pd.DataFrame()
            
            # Group by store
            store_perf = df.groupby('store_code').agg({
                'total_amount': 'sum',  # ✅ FIXED
                'quantity': 'sum',
                'transaction_id': 'count'
            }).reset_index()
            
            store_perf.columns = ['store_code', 'total_revenue', 'total_quantity', 'total_transactions']
            
            # Merge with store details
            stores = self.get_all_stores()
            if not stores.empty:
                store_perf = store_perf.merge(
                    stores[['store_code', 'store_name', 'city', 'state']], 
                    on='store_code', 
                    how='left'
                )
            
            # Calculate averages
            store_perf['avg_transaction_value'] = (
                store_perf['total_revenue'] / store_perf['total_transactions']
            ).round(2)
            
            return store_perf.sort_values('total_revenue', ascending=False)
        except Exception as e:
            print(f"Error calculating store performance: {e}")
            return pd.DataFrame()
    
    def get_store_product_performance(self, store_code):
        """Get top products for a specific store"""
        try:
            df = self.get_sales_by_store(store_code)
            if df.empty:
                return pd.DataFrame()
            
            product_perf = df.groupby('product_name').agg({
                'total_amount': 'sum',  # ✅ FIXED
                'quantity': 'sum',
                'transaction_id': 'count'
            }).reset_index()
            
            product_perf.columns = ['product_name', 'revenue', 'quantity_sold', 'transactions']
            return product_perf.sort_values('revenue', ascending=False)
        except Exception as e:
            print(f"Error fetching store product performance: {e}")
            return pd.DataFrame()
    
    def get_store_sales_trend(self, store_code, days=30):
        """Get daily sales trend for a store"""
        try:
            df = self.get_sales_by_store(store_code)
            if df.empty:
                return pd.DataFrame()
            
            # Filter last N days
            cutoff_date = df['transaction_date'].max() - timedelta(days=days)
            df = df[df['transaction_date'] >= cutoff_date]
            
            # Group by date
            daily_sales = df.groupby(df['transaction_date'].dt.date).agg({
                'total': 'sum',
                'quantity': 'sum',
                'transaction_id': 'count'
            }).reset_index()
            
            daily_sales.columns = ['date', 'revenue', 'quantity', 'transactions']
            return daily_sales
        except Exception as e:
            print(f"Error fetching store sales trend: {e}")
            return pd.DataFrame()


# ========================================
# CONVENIENCE FUNCTIONS (Backward Compatible)
# ========================================

def load_data() -> pd.DataFrame:
    """Backward compatible function"""
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
        
        print("=" * 60)
        print("TEST: Loading Sales")
        print("=" * 60)
        sales = db.get_all_sales()
        print(f"✅ Loaded {len(sales)} sales\n")
        
        if not sales.empty:
            print("Columns:", sales.columns.tolist())
            print("\nFirst row:")
            print(sales.head(1))
        
        print("🎉 Test Passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
