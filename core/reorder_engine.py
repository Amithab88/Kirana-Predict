"""
core/reorder_engine.py - Smart Reorder Calculation Engine
Analyzes sales patterns and generates intelligent reorder suggestions
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import math

try:
    from core.database_connection import get_supabase_client
    from core.inventory_manager import InventoryManager
except ImportError:
    from .database_connection import get_supabase_client
    from .inventory_manager import InventoryManager


class ReorderEngine:
    """
    Smart reorder calculation engine
    Analyzes consumption patterns and generates optimal reorder suggestions
    """
    
    def __init__(self):
        self.supabase = get_supabase_client()
        self.inventory = InventoryManager()
    
    # ============================================
    # CONSUMPTION ANALYSIS
    # ============================================
    
    def calculate_consumption_rate(self, product_name: str, store_code: str,
                                   days: int = 30) -> Dict:
        """
        Calculate daily consumption rate for a product
        
        Returns:
            {
                'daily_avg': float,
                'weekly_avg': float,
                'monthly_total': int,
                'trend': str,  # 'increasing', 'stable', 'decreasing'
                'confidence': float  # 0-1 based on data points
            }
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Get sales history
            response = self.supabase.table('sales')\
                .select('quantity, transaction_date')\
                .eq('product_name', product_name)\
                .eq('store_code', store_code)\
                .gte('transaction_date', cutoff_date)\
                .execute()
            
            if not response.data:
                return {
                    'daily_avg': 0,
                    'weekly_avg': 0,
                    'monthly_total': 0,
                    'trend': 'unknown',
                    'confidence': 0
                }
            
            df = pd.DataFrame(response.data)
            df['transaction_date'] = pd.to_datetime(df['transaction_date'])
            
            # Calculate totals
            total_sold = df['quantity'].sum()
            days_with_sales = len(df['transaction_date'].dt.date.unique())
            
            daily_avg = total_sold / days if days > 0 else 0
            weekly_avg = daily_avg * 7
            
            # Calculate trend (compare first half vs second half)
            midpoint = df['transaction_date'].min() + (df['transaction_date'].max() - df['transaction_date'].min()) / 2
            first_half = df[df['transaction_date'] <= midpoint]['quantity'].sum()
            second_half = df[df['transaction_date'] > midpoint]['quantity'].sum()
            
            if second_half > first_half * 1.2:
                trend = 'increasing'
            elif second_half < first_half * 0.8:
                trend = 'decreasing'
            else:
                trend = 'stable'
            
            # Confidence based on number of data points
            confidence = min(days_with_sales / 15, 1.0)  # Max confidence at 15+ days of sales
            
            return {
                'daily_avg': round(daily_avg, 2),
                'weekly_avg': round(weekly_avg, 2),
                'monthly_total': int(total_sold),
                'trend': trend,
                'confidence': round(confidence, 2),
                'days_analyzed': days,
                'sales_count': len(df)
            }
            
        except Exception as e:
            print(f"Error calculating consumption: {e}")
            return {
                'daily_avg': 0,
                'weekly_avg': 0,
                'monthly_total': 0,
                'trend': 'unknown',
                'confidence': 0
            }
    
    def predict_stockout_date(self, product_name: str, store_code: str) -> Optional[datetime]:
        """
        Predict when a product will run out of stock
        
        Returns:
            datetime when stock will reach 0, or None if not calculable
        """
        try:
            # Get current stock
            stock_info = self.inventory.get_current_stock(product_name, store_code)
            if not stock_info or stock_info['current_stock'] <= 0:
                return datetime.now()  # Already out of stock
            
            current_stock = stock_info['current_stock']
            
            # Get consumption rate
            consumption = self.calculate_consumption_rate(product_name, store_code, days=30)
            daily_avg = consumption['daily_avg']
            
            if daily_avg <= 0:
                return None  # No consumption history
            
            # Calculate days until stockout
            days_remaining = current_stock / daily_avg
            
            # Adjust based on trend
            if consumption['trend'] == 'increasing':
                days_remaining *= 0.8  # Stock will run out 20% faster
            elif consumption['trend'] == 'decreasing':
                days_remaining *= 1.2  # Stock will last 20% longer
            
            stockout_date = datetime.now() + timedelta(days=days_remaining)
            return stockout_date
            
        except Exception as e:
            print(f"Error predicting stockout: {e}")
            return None
    
    # ============================================
    # REORDER CALCULATIONS
    # ============================================
    
    def calculate_optimal_order_quantity(self, product_name: str, store_code: str,
                                        lead_time_days: int = 7,
                                        safety_stock_days: int = 7) -> Dict:
        """
        Calculate optimal reorder quantity using Economic Order Quantity (EOQ) principles
        
        Args:
            lead_time_days: Days from order to delivery
            safety_stock_days: Extra days of buffer stock
            
        Returns:
            {
                'reorder_quantity': int,
                'reorder_point': int,
                'safety_stock': int,
                'order_cost_estimate': float,
                'reasoning': str
            }
        """
        try:
            # Get consumption data
            consumption = self.calculate_consumption_rate(product_name, store_code)
            daily_avg = consumption['daily_avg']
            
            if daily_avg <= 0:
                return {
                    'reorder_quantity': 50,  # Default
                    'reorder_point': 10,
                    'safety_stock': 5,
                    'order_cost_estimate': 0,
                    'reasoning': 'No sales history - using default values'
                }
            
            # Calculate safety stock
            safety_stock = math.ceil(daily_avg * safety_stock_days)
            
            # Calculate reorder point (consumption during lead time + safety stock)
            reorder_point = math.ceil(daily_avg * lead_time_days) + safety_stock
            
            # Calculate order quantity (30 days supply)
            # Adjusted based on trend
            base_quantity = daily_avg * 30
            
            if consumption['trend'] == 'increasing':
                order_quantity = math.ceil(base_quantity * 1.3)  # Order 30% more
            elif consumption['trend'] == 'decreasing':
                order_quantity = math.ceil(base_quantity * 0.8)  # Order 20% less
            else:
                order_quantity = math.ceil(base_quantity)
            
            # Get unit cost for estimate
            stock_info = self.inventory.get_current_stock(product_name, store_code)
            unit_cost = stock_info.get('unit_cost', 0) if stock_info else 0
            order_cost = order_quantity * unit_cost
            
            reasoning = f"Based on {consumption['days_analyzed']} days of data. "
            reasoning += f"Daily consumption: {daily_avg:.1f} units. "
            reasoning += f"Trend: {consumption['trend']}. "
            reasoning += f"30-day supply with {safety_stock_days}-day safety buffer."
            
            return {
                'reorder_quantity': int(order_quantity),
                'reorder_point': int(reorder_point),
                'safety_stock': int(safety_stock),
                'order_cost_estimate': round(order_cost, 2),
                'daily_consumption': round(daily_avg, 2),
                'reasoning': reasoning,
                'confidence': consumption['confidence']
            }
            
        except Exception as e:
            print(f"Error calculating order quantity: {e}")
            return {
                'reorder_quantity': 50,
                'reorder_point': 10,
                'safety_stock': 5,
                'order_cost_estimate': 0,
                'reasoning': f'Error in calculation: {str(e)}'
            }
    
    def generate_reorder_suggestions(self, store_code: Optional[str] = None,
                                    priority: str = 'all') -> pd.DataFrame:
        """
        Generate comprehensive reorder suggestions for all products
        
        Args:
            store_code: Filter by store (None = all stores)
            priority: 'urgent', 'soon', 'all'
            
        Returns:
            DataFrame with reorder suggestions sorted by urgency
        """
        try:
            # Get all low stock items
            low_stock_df = self.inventory.get_low_stock_items(store_code)
            
            if low_stock_df.empty:
                return pd.DataFrame()
            
            suggestions = []
            
            for _, item in low_stock_df.iterrows():
                product_name = item['product_name']
                store = item['store_code']
                current_stock = item['current_stock']
                
                # Calculate consumption and order details
                consumption = self.calculate_consumption_rate(product_name, store)
                order_calc = self.calculate_optimal_order_quantity(product_name, store)
                stockout_date = self.predict_stockout_date(product_name, store)
                
                # Calculate urgency
                if stockout_date:
                    days_until_stockout = (stockout_date - datetime.now()).days
                else:
                    days_until_stockout = 999
                
                # Determine priority
                if days_until_stockout <= 3:
                    priority_level = 'URGENT'
                    priority_score = 3
                elif days_until_stockout <= 7:
                    priority_level = 'HIGH'
                    priority_score = 2
                elif days_until_stockout <= 14:
                    priority_level = 'MEDIUM'
                    priority_score = 1
                else:
                    priority_level = 'LOW'
                    priority_score = 0
                
                suggestions.append({
                    'product_name': product_name,
                    'store_code': store,
                    'current_stock': current_stock,
                    'reorder_point': item['reorder_point'],
                    'daily_consumption': consumption['daily_avg'],
                    'trend': consumption['trend'],
                    'days_until_stockout': days_until_stockout,
                    'stockout_date': stockout_date.strftime('%Y-%m-%d') if stockout_date else 'Unknown',
                    'suggested_order_qty': order_calc['reorder_quantity'],
                    'order_cost_estimate': order_calc['order_cost_estimate'],
                    'priority': priority_level,
                    'priority_score': priority_score,
                    'confidence': consumption['confidence'],
                    'reasoning': order_calc['reasoning']
                })
            
            df = pd.DataFrame(suggestions)
            
            # Filter by priority if requested
            if priority == 'urgent':
                df = df[df['priority'] == 'URGENT']
            elif priority == 'soon':
                df = df[df['priority'].isin(['URGENT', 'HIGH'])]
            
            # Sort by priority and days until stockout
            df = df.sort_values(['priority_score', 'days_until_stockout'], 
                               ascending=[False, True])
            
            return df
            
        except Exception as e:
            print(f"Error generating suggestions: {e}")
            return pd.DataFrame()
    
    # ============================================
    # REPORTING
    # ============================================
    
    def get_inventory_health_score(self, store_code: Optional[str] = None) -> Dict:
        """
        Calculate overall inventory health score (0-100)
        
        Factors:
        - % of items in stock
        - % of items at healthy levels
        - Stockout risk
        - Inventory turnover
        """
        try:
            all_stock = self.inventory.get_all_stock(store_code)
            
            if all_stock.empty:
                return {
                    'score': 0,
                    'grade': 'F',
                    'status': 'No inventory data'
                }
            
            total_items = len(all_stock)
            
            # Factor 1: Items in stock (weight: 30%)
            in_stock = len(all_stock[all_stock['current_stock'] > 0])
            stock_score = (in_stock / total_items) * 30
            
            # Factor 2: Items at healthy levels (weight: 40%)
            healthy = len(all_stock[all_stock['current_stock'] > all_stock['reorder_point']])
            healthy_score = (healthy / total_items) * 40
            
            # Factor 3: Critical items (weight: 30%)
            critical = len(all_stock[all_stock['current_stock'] <= 0])
            critical_penalty = (critical / total_items) * 30
            
            # Calculate final score
            total_score = stock_score + healthy_score + (30 - critical_penalty)
            total_score = round(total_score, 1)
            
            # Assign grade
            if total_score >= 90:
                grade = 'A'
                status = 'Excellent'
            elif total_score >= 80:
                grade = 'B'
                status = 'Good'
            elif total_score >= 70:
                grade = 'C'
                status = 'Fair'
            elif total_score >= 60:
                grade = 'D'
                status = 'Poor'
            else:
                grade = 'F'
                status = 'Critical'
            
            return {
                'score': total_score,
                'grade': grade,
                'status': status,
                'total_products': total_items,
                'in_stock': in_stock,
                'healthy_levels': healthy,
                'critical_items': critical,
                'out_of_stock': len(all_stock[all_stock['current_stock'] <= 0])
            }
            
        except Exception as e:
            print(f"Error calculating health score: {e}")
            return {
                'score': 0,
                'grade': 'F',
                'status': 'Error calculating'
            }


# ========================================
# TESTING
# ========================================

if __name__ == "__main__":
    print("🔄 Testing Reorder Engine...\n")
    
    try:
        engine = ReorderEngine()
        
        print("=" * 60)
        print("TEST: Generate Reorder Suggestions")
        print("=" * 60)
        suggestions = engine.generate_reorder_suggestions(store_code='STORE001')
        
        if not suggestions.empty:
            print(f"✅ {len(suggestions)} reorder suggestions generated\n")
            print(suggestions[['product_name', 'current_stock', 'priority', 
                             'days_until_stockout', 'suggested_order_qty']].head())
        else:
            print("ℹ️  No reorder suggestions (all stock levels healthy)")
        
        print("\n" + "=" * 60)
        print("TEST: Inventory Health Score")
        print("=" * 60)
        health = engine.get_inventory_health_score('STORE001')
        print(f"Score: {health['score']}/100 (Grade: {health['grade']})")
        print(f"Status: {health['status']}")
        print(f"Products: {health['total_products']}")
        print(f"In Stock: {health['in_stock']}")
        print(f"Critical: {health['critical_items']}")
        
        print("\n🎉 Tests Passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
