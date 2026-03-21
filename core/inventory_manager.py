"""
core/inventory_manager.py - Inventory Management Engine
Handles real-time stock tracking, auto-deduction, and reorder logic
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

try:
    from core.database_connection import get_supabase_client
except ImportError:
    from database_connection import get_supabase_client


class InventoryManager:
    """
    Manages inventory stock levels, movements, and reorder alerts
    """
    
    def __init__(self):
        """Initialize inventory manager"""
        self.supabase = get_supabase_client()
    
    # ============================================
    # STOCK TRACKING METHODS
    # ============================================
    
    def get_current_stock(self, product_name: str, store_code: str) -> Optional[Dict]:
        """Get current stock level for a product at a store"""
        try:
            response = self.supabase.table('inventory_stock')\
                .select('*')\
                .eq('product_name', product_name)\
                .eq('store_code', store_code)\
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            print(f"❌ Error fetching stock: {e}")
            return None
    
    def get_all_stock(self, store_code: Optional[str] = None) -> pd.DataFrame:
        """Get all inventory stock, optionally filtered by store"""
        try:
            query = self.supabase.table('inventory_stock').select('*')
            if store_code:
                query = query.eq('store_code', store_code)
            
            response = query.order('product_name').execute()
            return pd.DataFrame(response.data) if response.data else pd.DataFrame()
        except Exception as e:
            print(f"❌ Error fetching all stock: {e}")
            return pd.DataFrame()
    
    def get_low_stock_items(self, store_code: Optional[str] = None) -> pd.DataFrame:
        """Get items that are at or below reorder point"""
        try:
            df = self.get_all_stock(store_code)
            if df.empty:
                return df
            
            low_stock = df[df['current_stock'] <= df['reorder_point']]
            low_stock['units_needed'] = low_stock['reorder_point'] - low_stock['current_stock']
            
            return low_stock.sort_values('current_stock')
        except Exception as e:
            print(f"❌ Error fetching low stock: {e}")
            return pd.DataFrame()
    
    # ============================================
    # STOCK DEDUCTION (ON SALE)
    # ============================================
    
    def deduct_stock_on_sale(self, product_name: str, store_code: str, 
                             quantity: int, transaction_id: str,
                             unit_price: float = 0) -> Tuple[bool, str]:
        """
        Deduct stock when a sale happens
        Returns: (success: bool, message: str)
        """
        try:
            # Get current stock
            stock_record = self.get_current_stock(product_name, store_code)
            
            if not stock_record:
                # Product not in inventory - create it with 0 stock
                self._initialize_product_stock(product_name, store_code, quantity=0)
                return False, f"⚠️ Product '{product_name}' not in inventory. Stock initialized to 0."
            
            current_stock = stock_record['current_stock']
            new_stock = current_stock - quantity
            
            # Allow negative stock (for tracking backorders)
            # Update stock level
            self.supabase.table('inventory_stock')\
                .update({
                    'current_stock': new_stock,
                    'last_updated': datetime.now().isoformat()
                })\
                .eq('product_name', product_name)\
                .eq('store_code', store_code)\
                .execute()
            
            # Log movement
            self._log_stock_movement(
                product_name=product_name,
                store_code=store_code,
                movement_type='SALE',
                quantity=-quantity,  # Negative for stock out
                previous_stock=current_stock,
                new_stock=new_stock,
                reference_id=transaction_id,
                unit_cost=unit_price
            )
            
            # Check if reorder needed
            if new_stock <= stock_record['reorder_point']:
                self._create_reorder_alert(product_name, store_code, new_stock, stock_record)
                return True, f"✅ Stock deducted. ⚠️ Low stock alert created!"
            
            return True, f"✅ Stock deducted: {current_stock} → {new_stock}"
            
        except Exception as e:
            return False, f"❌ Error deducting stock: {e}"
    
    # ============================================
    # STOCK ADDITION (ON PURCHASE)
    # ============================================
    
    def add_stock_on_purchase(self, product_name: str, store_code: str,
                              quantity: int, unit_cost: float,
                              reference_id: str = None) -> Tuple[bool, str]:
        """
        Add stock when new inventory arrives
        Returns: (success: bool, message: str)
        """
        try:
            stock_record = self.get_current_stock(product_name, store_code)
            
            if not stock_record:
                # Initialize new product
                self._initialize_product_stock(product_name, store_code, quantity, unit_cost)
                self._log_stock_movement(
                    product_name=product_name,
                    store_code=store_code,
                    movement_type='PURCHASE',
                    quantity=quantity,
                    previous_stock=0,
                    new_stock=quantity,
                    reference_id=reference_id,
                    unit_cost=unit_cost
                )
                return True, f"✅ New product added with {quantity} units"
            
            current_stock = stock_record['current_stock']
            new_stock = current_stock + quantity
            
            # Update stock
            self.supabase.table('inventory_stock')\
                .update({
                    'current_stock': new_stock,
                    'unit_cost': unit_cost,
                    'last_restocked': datetime.now().isoformat(),
                    'last_updated': datetime.now().isoformat()
                })\
                .eq('product_name', product_name)\
                .eq('store_code', store_code)\
                .execute()
            
            # Log movement
            self._log_stock_movement(
                product_name=product_name,
                store_code=store_code,
                movement_type='PURCHASE',
                quantity=quantity,
                previous_stock=current_stock,
                new_stock=new_stock,
                reference_id=reference_id,
                unit_cost=unit_cost
            )
            
            # Cancel any pending reorder alerts
            self._cancel_reorder_alert(product_name, store_code)
            
            return True, f"✅ Stock added: {current_stock} → {new_stock}"
            
        except Exception as e:
            return False, f"❌ Error adding stock: {e}"
    
    # ============================================
    # STOCK MOVEMENTS LOG
    # ============================================
    
    def _log_stock_movement(self, product_name: str, store_code: str,
                           movement_type: str, quantity: int,
                           previous_stock: int, new_stock: int,
                           reference_id: str = None, unit_cost: float = 0,
                           notes: str = None):
        """Log all stock movements for audit trail"""
        try:
            movement_data = {
                'product_name': product_name,
                'store_code': store_code,
                'movement_type': movement_type,
                'quantity': quantity,
                'previous_stock': previous_stock,
                'new_stock': new_stock,
                'reference_id': reference_id,
                'unit_cost': unit_cost,
                'total_value': abs(quantity) * unit_cost,
                'notes': notes,
                'movement_date': datetime.now().isoformat()
            }
            
            self.supabase.table('stock_movements').insert(movement_data).execute()
        except Exception as e:
            print(f"⚠️ Error logging movement: {e}")
    
    def get_stock_movements(self, product_name: Optional[str] = None,
                           store_code: Optional[str] = None,
                           days: int = 30) -> pd.DataFrame:
        """Get stock movement history"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            query = self.supabase.table('stock_movements')\
                .select('*')\
                .gte('movement_date', cutoff_date)
            
            if product_name:
                query = query.eq('product_name', product_name)
            if store_code:
                query = query.eq('store_code', store_code)
            
            response = query.order('movement_date', desc=True).execute()
            return pd.DataFrame(response.data) if response.data else pd.DataFrame()
        except Exception as e:
            print(f"❌ Error fetching movements: {e}")
            return pd.DataFrame()
    
    # ============================================
    # REORDER ALERTS
    # ============================================
    
    def _create_reorder_alert(self, product_name: str, store_code: str,
                             current_stock: int, stock_record: Dict):
        """Create a reorder alert for low stock"""
        try:
            # Calculate daily average sales
            daily_avg = self._calculate_daily_avg_sales(product_name, store_code)
            
            # Calculate days until stockout
            if daily_avg > 0:
                days_left = current_stock / daily_avg
            else:
                days_left = 999  # No sales history
            
            alert_data = {
                'product_name': product_name,
                'store_code': store_code,
                'current_stock': current_stock,
                'reorder_point': stock_record['reorder_point'],
                'reorder_quantity': stock_record['reorder_quantity'],
                'days_until_stockout': round(days_left, 2),
                'daily_avg_sales': round(daily_avg, 2),
                'status': 'PENDING',
                'alert_date': datetime.now().isoformat()
            }
            
            # Check if alert already exists
            existing = self.supabase.table('reorder_alerts')\
                .select('id')\
                .eq('product_name', product_name)\
                .eq('store_code', store_code)\
                .eq('status', 'PENDING')\
                .execute()
            
            if not existing.data:
                self.supabase.table('reorder_alerts').insert(alert_data).execute()
                print(f"🔔 Reorder alert created: {product_name} @ {store_code}")
        except Exception as e:
            print(f"⚠️ Error creating reorder alert: {e}")
    
    def _cancel_reorder_alert(self, product_name: str, store_code: str):
        """Cancel pending reorder alerts when stock is replenished"""
        try:
            self.supabase.table('reorder_alerts')\
                .update({'status': 'RECEIVED'})\
                .eq('product_name', product_name)\
                .eq('store_code', store_code)\
                .eq('status', 'PENDING')\
                .execute()
        except Exception as e:
            print(f"⚠️ Error cancelling alert: {e}")
    
    def get_reorder_alerts(self, store_code: Optional[str] = None,
                          status: str = 'PENDING') -> pd.DataFrame:
        """Get reorder alerts"""
        try:
            query = self.supabase.table('reorder_alerts').select('*')
            
            if store_code:
                query = query.eq('store_code', store_code)
            if status:
                query = query.eq('status', status)
            
            response = query.order('days_until_stockout').execute()
            return pd.DataFrame(response.data) if response.data else pd.DataFrame()
        except Exception as e:
            print(f"❌ Error fetching alerts: {e}")
            return pd.DataFrame()
    
    # ============================================
    # HELPER METHODS
    # ============================================
    
    def _initialize_product_stock(self, product_name: str, store_code: str,
                                  quantity: int = 0, unit_cost: float = 0):
        """Initialize a new product in inventory"""
        try:
            stock_data = {
                'product_name': product_name,
                'store_code': store_code,
                'current_stock': quantity,
                'reorder_point': 10,  # Default
                'reorder_quantity': 50,  # Default
                'unit_cost': unit_cost,
                'last_updated': datetime.now().isoformat()
            }
            
            self.supabase.table('inventory_stock').insert(stock_data).execute()
        except Exception as e:
            print(f"⚠️ Error initializing stock: {e}")
    
    def _calculate_daily_avg_sales(self, product_name: str, store_code: str,
                                   days: int = 30) -> float:
        """Calculate average daily sales for a product"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            response = self.supabase.table('sales')\
                .select('quantity')\
                .eq('product_name', product_name)\
                .eq('store_code', store_code)\
                .gte('transaction_date', cutoff_date)\
                .execute()
            
            if response.data:
                total_sold = sum(item['quantity'] for item in response.data)
                return total_sold / days
            return 0.0
        except Exception as e:
            print(f"⚠️ Error calculating avg sales: {e}")
            return 0.0
    
    # ============================================
    # INVENTORY VALUATION
    # ============================================
    
    def get_inventory_value(self, store_code: Optional[str] = None) -> Dict:
        """Calculate total inventory value"""
        try:
            df = self.get_all_stock(store_code)
            if df.empty:
                return {'total_units': 0, 'total_value': 0}
            
            df['stock_value'] = df['current_stock'] * df['unit_cost']
            
            return {
                'total_units': int(df['current_stock'].sum()),
                'total_value': float(df['stock_value'].sum()),
                'product_count': len(df),
                'low_stock_count': len(df[df['current_stock'] <= df['reorder_point']])
            }
        except Exception as e:
            print(f"❌ Error calculating inventory value: {e}")
            return {'total_units': 0, 'total_value': 0}


# ========================================
# TESTING
# ========================================

if __name__ == "__main__":
    print("🔄 Testing Inventory Manager...\n")
    
    try:
        inv = InventoryManager()
        
        print("=" * 60)
        print("TEST: Get All Stock")
        print("=" * 60)
        stock = inv.get_all_stock()
        print(f"✅ Loaded {len(stock)} products in inventory\n")
        
        if not stock.empty:
            print(stock.head())
        
        print("\n" + "=" * 60)
        print("TEST: Get Low Stock Items")
        print("=" * 60)
        low_stock = inv.get_low_stock_items()
        print(f"⚠️ {len(low_stock)} items need reordering\n")
        
        if not low_stock.empty:
            print(low_stock[['product_name', 'store_code', 'current_stock', 'reorder_point']])
        
        print("\n🎉 Tests Passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
