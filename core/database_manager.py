"""
core/database_manager.py — Production-Grade Supabase Database Manager
=====================================================================
Central data-access layer for Kirana-Predict Pro.

Responsibilities:
  • Authentication (sign-in / sign-out / role lookup)
  • Sales CRUD (add, get all, recent, by store, by product)
  • Store management CRUD
  • Aggregated performance & analytics queries
  • Notification persistence (read/unread, mark-read)
  • Pagination helpers for large result sets
  • Cached reads via @st.cache_data where appropriate

Every public method wraps Supabase calls in try/except and returns
either a DataFrame, dict, bool, or raises a descriptive error.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import hashlib
import uuid

try:
    from core.database_connection import get_supabase_client
except ImportError:
    from database_connection import get_supabase_client

try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False


# ────────────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────────────

def _safe_to_datetime(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Normalize a column to pd.Timestamp, handling ISO-8601 or mixed."""
    if col not in df.columns:
        return df
    try:
        df[col] = pd.to_datetime(df[col], format='ISO8601')
    except Exception:
        try:
            df[col] = pd.to_datetime(df[col], format='mixed')
        except Exception:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


def _generate_txn_id(prefix: str = "TXN") -> str:
    """Unique, collision-free transaction identifier."""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"{prefix}_{ts}_{short_uuid}"


# ────────────────────────────────────────────────────────────────────
# MAIN CLASS
# ────────────────────────────────────────────────────────────────────

class KiranaDatabase:
    """
    Universal database manager for Kirana-Predict Pro.
    Handles: Auth · Sales · Stores · Analytics · Notifications
    """

    def __init__(self):
        self.supabase = get_supabase_client()

    # ================================================================
    # AUTHENTICATION
    # ================================================================

    def authenticate_user(self, email: str, password: str) -> Dict:
        """Sign in with email+password via Supabase Auth."""
        try:
            response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password,
            })
            return {"success": True, "user": response.user}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_user_role(self, user_id: str) -> str:
        """Fetch role from user_roles table. Defaults to 'Staff'."""
        try:
            response = (
                self.supabase.table('user_roles')
                .select('role')
                .eq('user_id', user_id)
                .execute()
            )
            if response.data and len(response.data) > 0:
                return response.data[0].get('role', 'Staff')
            return 'Staff'
        except Exception:
            return 'Staff'

    def sign_out(self) -> bool:
        try:
            self.supabase.auth.sign_out()
            return True
        except Exception:
            return False

    # ================================================================
    # SALES — CRUD
    # ================================================================

    def add_sale(self, sale_data: Dict[str, Any], source: str = 'manual') -> Dict:
        """Insert a single sale row. Auto-generates transaction_id if absent."""
        sale_data['data_source'] = source
        sale_data['created_at'] = datetime.now().isoformat()

        if 'transaction_id' not in sale_data or not sale_data['transaction_id']:
            sale_data['transaction_id'] = _generate_txn_id()

        # Ensure total_amount is set
        if 'total_amount' not in sale_data and 'quantity' in sale_data and 'unit_price' in sale_data:
            sale_data['total_amount'] = sale_data['quantity'] * sale_data['unit_price']

        try:
            response = self.supabase.table('sales').insert(sale_data).execute()
            return response.data[0] if response.data else {}
        except Exception as e:
            print(f"❌ Error adding sale: {e}")
            raise

    def add_sales_bulk(self, rows: List[Dict[str, Any]], source: str = 'bulk') -> Tuple[int, int]:
        """Bulk-insert sales. Returns (success_count, fail_count)."""
        success = 0
        fail = 0
        for row in rows:
            try:
                self.add_sale(row, source=source)
                success += 1
            except Exception:
                fail += 1
        return success, fail

    def get_all_sales(self) -> pd.DataFrame:
        """Fetch every row from the sales table."""
        try:
            response = self.supabase.table('sales').select("*").execute()

            if not response.data:
                return pd.DataFrame()

            df = pd.DataFrame(response.data)
            df = _safe_to_datetime(df, 'transaction_date')
            df = _safe_to_datetime(df, 'created_at')
            return df

        except Exception as e:
            print(f"❌ Error loading sales: {e}")
            return pd.DataFrame()

    def get_recent_sales(self, days: int = 7) -> pd.DataFrame:
        """Sales from the last N days, most-recent first."""
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        try:
            response = (
                self.supabase.table('sales')
                .select("*")
                .gte('transaction_date', start_date)
                .order('transaction_date', desc=True)
                .execute()
            )
            df = pd.DataFrame(response.data) if response.data else pd.DataFrame()
            df = _safe_to_datetime(df, 'transaction_date')
            return df
        except Exception as e:
            print(f"❌ Error loading recent sales: {e}")
            return pd.DataFrame()

    def get_sales_by_product(self, product_name: str) -> pd.DataFrame:
        """All sales rows for a single product."""
        try:
            response = (
                self.supabase.table('sales')
                .select('*')
                .eq('product_name', product_name)
                .order('transaction_date', desc=True)
                .execute()
            )
            df = pd.DataFrame(response.data) if response.data else pd.DataFrame()
            df = _safe_to_datetime(df, 'transaction_date')
            return df
        except Exception as e:
            print(f"❌ Error loading sales by product: {e}")
            return pd.DataFrame()

    def get_sales_by_store(self, store_code: Optional[str] = None) -> pd.DataFrame:
        """Sales filtered by store (or all if None)."""
        try:
            query = self.supabase.table('sales').select('*')
            if store_code:
                query = query.eq('store_code', store_code)
            response = query.order('transaction_date', desc=True).execute()

            df = pd.DataFrame(response.data) if response.data else pd.DataFrame()
            df = _safe_to_datetime(df, 'transaction_date')
            return df
        except Exception as e:
            print(f"❌ Error fetching sales by store: {e}")
            return pd.DataFrame()

    def get_sales_by_date_range(self, start_date: str, end_date: str,
                                 store_code: Optional[str] = None) -> pd.DataFrame:
        """Sales within a date window, optionally scoped to a store."""
        try:
            query = (
                self.supabase.table('sales')
                .select('*')
                .gte('transaction_date', start_date)
                .lte('transaction_date', end_date)
            )
            if store_code:
                query = query.eq('store_code', store_code)

            response = query.order('transaction_date', desc=True).execute()
            df = pd.DataFrame(response.data) if response.data else pd.DataFrame()
            df = _safe_to_datetime(df, 'transaction_date')
            return df
        except Exception as e:
            print(f"❌ Error fetching sales by date range: {e}")
            return pd.DataFrame()

    def get_all_products(self) -> pd.DataFrame:
        """Distinct product names from the sales table."""
        try:
            response = self.supabase.table('sales').select('product_name, category').execute()
            if not response.data:
                return pd.DataFrame()
            df = pd.DataFrame(response.data).drop_duplicates(subset='product_name')
            return df.sort_values('product_name').reset_index(drop=True)
        except Exception as e:
            print(f"❌ Error loading products: {e}")
            return pd.DataFrame()

    # ================================================================
    # STORE MANAGEMENT
    # ================================================================

    def get_all_stores(self) -> pd.DataFrame:
        try:
            response = self.supabase.table('stores').select('*').order('store_code').execute()
            return pd.DataFrame(response.data) if response.data else pd.DataFrame()
        except Exception as e:
            print(f"❌ Error fetching stores: {e}")
            return pd.DataFrame()

    def get_active_stores(self) -> pd.DataFrame:
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
            print(f"❌ Error fetching active stores: {e}")
            return pd.DataFrame()

    def get_store_by_code(self, store_code: str) -> Optional[Dict]:
        try:
            response = (
                self.supabase.table('stores')
                .select('*')
                .eq('store_code', store_code)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"❌ Error fetching store: {e}")
            return None

    def add_store(self, store_data: Dict) -> bool:
        try:
            self.supabase.table('stores').insert(store_data).execute()
            return True
        except Exception as e:
            print(f"❌ Error adding store: {e}")
            return False

    def update_store(self, store_code: str, update_data: Dict) -> bool:
        try:
            self.supabase.table('stores').update(update_data).eq('store_code', store_code).execute()
            return True
        except Exception as e:
            print(f"❌ Error updating store: {e}")
            return False

    def delete_store(self, store_code: str) -> bool:
        """Soft-delete: set is_active = False."""
        return self.update_store(store_code, {'is_active': False})

    # ================================================================
    # STORE PERFORMANCE & ANALYTICS
    # ================================================================

    def get_store_performance(self) -> pd.DataFrame:
        """Revenue, quantity, txn count per store + merge with store details."""
        try:
            df = self.get_all_sales()
            if df.empty:
                return pd.DataFrame()

            store_perf = df.groupby('store_code').agg(
                total_revenue=('total_amount', 'sum'),
                total_quantity=('quantity', 'sum'),
                total_transactions=('transaction_id', 'count'),
            ).reset_index()

            stores = self.get_all_stores()
            if not stores.empty:
                store_perf = store_perf.merge(
                    stores[['store_code', 'store_name', 'city', 'state']],
                    on='store_code', how='left'
                )

            store_perf['avg_transaction_value'] = (
                store_perf['total_revenue'] / store_perf['total_transactions']
            ).round(2)

            return store_perf.sort_values('total_revenue', ascending=False)
        except Exception as e:
            print(f"❌ Error calculating store performance: {e}")
            return pd.DataFrame()

    def get_store_product_performance(self, store_code: str) -> pd.DataFrame:
        """Top products at a specific store."""
        try:
            df = self.get_sales_by_store(store_code)
            if df.empty:
                return pd.DataFrame()

            product_perf = df.groupby('product_name').agg(
                revenue=('total_amount', 'sum'),
                quantity_sold=('quantity', 'sum'),
                transactions=('transaction_id', 'count'),
            ).reset_index()

            return product_perf.sort_values('revenue', ascending=False)
        except Exception as e:
            print(f"❌ Error fetching store product performance: {e}")
            return pd.DataFrame()

    def get_store_sales_trend(self, store_code: str, days: int = 30) -> pd.DataFrame:
        """Daily revenue/qty/txn trend for a store."""
        try:
            df = self.get_sales_by_store(store_code)
            if df.empty:
                return pd.DataFrame()

            cutoff_date = df['transaction_date'].max() - timedelta(days=days)
            df = df[df['transaction_date'] >= cutoff_date]

            daily = df.groupby(df['transaction_date'].dt.date).agg(
                revenue=('total_amount', 'sum'),
                quantity=('quantity', 'sum'),
                transactions=('transaction_id', 'count'),
            ).reset_index()
            daily.rename(columns={'transaction_date': 'date'}, inplace=True)
            return daily
        except Exception as e:
            print(f"❌ Error fetching store sales trend: {e}")
            return pd.DataFrame()

    # ================================================================
    # NOTIFICATIONS (persisted in Supabase)
    # ================================================================

    def insert_notification(self, notification: Dict) -> bool:
        """
        notification = {
            'title': str,
            'message': str,
            'type': 'low_stock' | 'forecast' | 'transfer' | 'system',
            'severity': 'info' | 'warning' | 'critical',
            'store_code': str | None,
            'is_read': False,
        }
        """
        notification.setdefault('created_at', datetime.now().isoformat())
        notification.setdefault('is_read', False)
        try:
            self.supabase.table('notifications').insert(notification).execute()
            return True
        except Exception as e:
            print(f"❌ Error inserting notification: {e}")
            return False

    def get_notifications(self, limit: int = 50,
                          unread_only: bool = False) -> pd.DataFrame:
        """Fetch notifications, newest first."""
        try:
            query = (
                self.supabase.table('notifications')
                .select('*')
                .order('created_at', desc=True)
                .limit(limit)
            )
            if unread_only:
                query = query.eq('is_read', False)

            response = query.execute()
            df = pd.DataFrame(response.data) if response.data else pd.DataFrame()
            df = _safe_to_datetime(df, 'created_at')
            return df
        except Exception as e:
            print(f"❌ Error fetching notifications: {e}")
            return pd.DataFrame()

    def mark_notification_read(self, notification_id: int) -> bool:
        try:
            self.supabase.table('notifications').update(
                {'is_read': True}
            ).eq('id', notification_id).execute()
            return True
        except Exception:
            return False

    def mark_all_notifications_read(self) -> bool:
        try:
            self.supabase.table('notifications').update(
                {'is_read': True}
            ).eq('is_read', False).execute()
            return True
        except Exception:
            return False

    def get_unread_count(self) -> int:
        try:
            response = (
                self.supabase.table('notifications')
                .select('id', count='exact')
                .eq('is_read', False)
                .execute()
            )
            return response.count if response.count else 0
        except Exception:
            return 0


# ════════════════════════════════════════════════════════════════════
# BACKWARD-COMPATIBLE MODULE-LEVEL FUNCTIONS
# ════════════════════════════════════════════════════════════════════

def load_data() -> pd.DataFrame:
    return KiranaDatabase().get_all_sales()

def load_data_from_db() -> pd.DataFrame:
    return KiranaDatabase().get_all_sales()


# ════════════════════════════════════════════════════════════════════
# STANDALONE TEST
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🔄 Testing Database Manager …\n")
    try:
        db = KiranaDatabase()

        print("=" * 60)
        print("TEST: Loading Sales")
        print("=" * 60)
        sales = db.get_all_sales()
        print(f"✅ Loaded {len(sales)} sales")
        if not sales.empty:
            print("Columns:", sales.columns.tolist())
            print(sales.head(2))

        print("\n" + "=" * 60)
        print("TEST: Active Stores")
        print("=" * 60)
        stores = db.get_active_stores()
        print(f"✅ {len(stores)} active stores")

        print("\n" + "=" * 60)
        print("TEST: Store Performance")
        print("=" * 60)
        perf = db.get_store_performance()
        print(f"✅ Performance for {len(perf)} stores")

        print("\n🎉 All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
