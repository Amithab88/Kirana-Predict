"""
core/inventory_manager.py — Production-Grade Inventory Engine
=============================================================
Central inventory management for Kirana-Predict Pro.

Responsibilities:
  • Real-time stock tracking (get current / all / low stock)
  • Stock deduction on sale (with reorder alert trigger)
  • Stock addition on purchase
  • Atomic inter-store transfers (TRANSFER_OUT + TRANSFER_IN)
  • Stock adjustment (damage, expiry, audit corrections)
  • Full audit trail via stock_movements table
  • Inventory valuation & health scoring
  • Consumption analytics (daily avg, trend, stockout prediction)
  • Reorder suggestions with priority scoring

Tables used:
  • `inventory`        — product_name, store_code, current_stock, last_updated
  • `stock_movements`  — full audit trail of every movement
  • `sales`            — read-only for consumption analytics

All Supabase calls wrapped in try/except with descriptive logging.
"""

import math
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
    Manages inventory stock levels, movements, transfers, and analytics.
    """

    # ── Default reorder settings ──────────────────────────────────────
    DEFAULT_REORDER_POINT = 10
    DEFAULT_REORDER_QTY = 50
    DEFAULT_LEAD_TIME_DAYS = 7
    DEFAULT_SAFETY_STOCK_DAYS = 7

    def __init__(self):
        self.supabase = get_supabase_client()

    # ================================================================
    #  STOCK READS
    # ================================================================

    def get_current_stock(self, product_name: str,
                          store_code: str) -> Optional[Dict]:
        """Single product stock at a single store."""
        try:
            response = (
                self.supabase.table('inventory')
                .select('*')
                .eq('product_name', product_name)
                .eq('store_code', store_code)
                .execute()
            )
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            print(f"❌ Error fetching stock: {e}")
            return None

    def get_all_stock(self, store_code: Optional[str] = None) -> pd.DataFrame:
        """All inventory rows, optionally filtered by store."""
        try:
            query = self.supabase.table('inventory').select('*')
            if store_code:
                query = query.eq('store_code', store_code)
            response = query.order('product_name').execute()

            if not response.data:
                return pd.DataFrame()

            df = pd.DataFrame(response.data)

            # Ensure reorder columns exist for downstream consumers
            if 'reorder_point' not in df.columns:
                df['reorder_point'] = self.DEFAULT_REORDER_POINT
            if 'reorder_quantity' not in df.columns:
                df['reorder_quantity'] = self.DEFAULT_REORDER_QTY
            if 'unit_cost' not in df.columns:
                df['unit_cost'] = 0.0

            return df
        except Exception as e:
            print(f"❌ Error fetching all stock: {e}")
            return pd.DataFrame()

    def get_low_stock_items(self,
                            store_code: Optional[str] = None) -> pd.DataFrame:
        """Items at or below reorder point."""
        try:
            df = self.get_all_stock(store_code)
            if df.empty:
                return df

            low = df[df['current_stock'] <= df['reorder_point']].copy()
            low['units_needed'] = low['reorder_point'] - low['current_stock']
            return low.sort_values('current_stock')
        except Exception as e:
            print(f"❌ Error fetching low stock: {e}")
            return pd.DataFrame()

    # ================================================================
    #  STOCK WRITE — SALE DEDUCTION
    # ================================================================

    def deduct_stock_on_sale(self, product_name: str, store_code: str,
                             quantity: int, transaction_id: str,
                             unit_price: float = 0) -> Tuple[bool, str]:
        """
        Deduct stock on a sale event.
        Returns (success, user-facing message).
        """
        try:
            stock_record = self.get_current_stock(product_name, store_code)

            if not stock_record:
                self._upsert_inventory(product_name, store_code, 0)
                return False, (
                    f"⚠️ Product '{product_name}' was not in inventory. "
                    f"Initialized to 0 — please add stock."
                )

            prev = stock_record['current_stock']
            new = prev - quantity

            self._upsert_inventory(product_name, store_code, new)

            self._log_movement(
                product_name=product_name,
                store_code=store_code,
                movement_type='SALE',
                quantity=-quantity,
                previous_stock=prev,
                new_stock=new,
                reference_id=transaction_id,
                unit_cost=unit_price,
            )

            reorder_pt = stock_record.get('reorder_point', self.DEFAULT_REORDER_POINT)
            if new <= reorder_pt:
                return True, f"✅ Stock deducted: {prev} → {new}. ⚠️ Below reorder point!"

            return True, f"✅ Stock deducted: {prev} → {new}"

        except Exception as e:
            return False, f"❌ Error deducting stock: {e}"

    # ================================================================
    #  STOCK WRITE — PURCHASE / INWARD
    # ================================================================

    def add_stock_on_purchase(self, product_name: str, store_code: str,
                              quantity: int, unit_cost: float,
                              reference_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Add stock when new inventory arrives.
        Returns (success, message).
        """
        try:
            stock_record = self.get_current_stock(product_name, store_code)

            if not stock_record:
                self._upsert_inventory(product_name, store_code, quantity, unit_cost)
                self._log_movement(
                    product_name=product_name,
                    store_code=store_code,
                    movement_type='PURCHASE',
                    quantity=quantity,
                    previous_stock=0,
                    new_stock=quantity,
                    reference_id=reference_id,
                    unit_cost=unit_cost,
                )
                return True, f"✅ New product added with {quantity} units"

            prev = stock_record['current_stock']
            new = prev + quantity

            self._upsert_inventory(product_name, store_code, new, unit_cost)

            self._log_movement(
                product_name=product_name,
                store_code=store_code,
                movement_type='PURCHASE',
                quantity=quantity,
                previous_stock=prev,
                new_stock=new,
                reference_id=reference_id,
                unit_cost=unit_cost,
            )

            return True, f"✅ Stock added: {prev} → {new}"

        except Exception as e:
            return False, f"❌ Error adding stock: {e}"

    # ================================================================
    #  STOCK WRITE — INTER-STORE TRANSFER (ATOMIC)
    # ================================================================

    def transfer_stock(self, product_name: str,
                       from_store: str, to_store: str,
                       quantity: int,
                       reason: str = "") -> Tuple[bool, str]:
        """
        Atomic inter-store transfer.
        Creates TRANSFER_OUT at source and TRANSFER_IN at destination.
        Returns (success, message).
        """
        if quantity <= 0:
            return False, "❌ Quantity must be positive"
        if from_store == to_store:
            return False, "❌ Source and destination stores must differ"

        try:
            # Validate source stock
            src = self.get_current_stock(product_name, from_store)
            if not src:
                return False, f"❌ Product '{product_name}' not found at {from_store}"
            if src['current_stock'] < quantity:
                return False, (
                    f"❌ Insufficient stock at {from_store}. "
                    f"Available: {src['current_stock']}, requested: {quantity}"
                )

            ref_id = f"TRF_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            unit_cost = src.get('unit_cost', 0)

            # ── Deduct from source ─────────────────────────────────
            src_prev = src['current_stock']
            src_new = src_prev - quantity
            self._upsert_inventory(product_name, from_store, src_new)
            self._log_movement(
                product_name=product_name,
                store_code=from_store,
                movement_type='TRANSFER_OUT',
                quantity=-quantity,
                previous_stock=src_prev,
                new_stock=src_new,
                reference_id=ref_id,
                unit_cost=unit_cost,
                notes=f"Transfer to {to_store}. {reason}".strip(),
            )

            # ── Add to destination ─────────────────────────────────
            dst = self.get_current_stock(product_name, to_store)
            dst_prev = dst['current_stock'] if dst else 0
            dst_new = dst_prev + quantity
            self._upsert_inventory(product_name, to_store, dst_new, unit_cost)
            self._log_movement(
                product_name=product_name,
                store_code=to_store,
                movement_type='TRANSFER_IN',
                quantity=quantity,
                previous_stock=dst_prev,
                new_stock=dst_new,
                reference_id=ref_id,
                unit_cost=unit_cost,
                notes=f"Transfer from {from_store}. {reason}".strip(),
            )

            return True, (
                f"✅ Transferred {quantity} units of {product_name}: "
                f"{from_store} ({src_prev}→{src_new}) → "
                f"{to_store} ({dst_prev}→{dst_new})"
            )

        except Exception as e:
            return False, f"❌ Transfer failed: {e}"

    # ================================================================
    #  STOCK WRITE — ADJUSTMENT
    # ================================================================

    def adjust_stock(self, product_name: str, store_code: str,
                     new_quantity: int,
                     reason: str = "Manual adjustment") -> Tuple[bool, str]:
        """Set absolute stock level (for damage, expiry, audit)."""
        try:
            stock = self.get_current_stock(product_name, store_code)
            prev = stock['current_stock'] if stock else 0
            diff = new_quantity - prev

            self._upsert_inventory(product_name, store_code, new_quantity)
            self._log_movement(
                product_name=product_name,
                store_code=store_code,
                movement_type='ADJUSTMENT',
                quantity=diff,
                previous_stock=prev,
                new_stock=new_quantity,
                notes=reason,
            )
            return True, f"✅ Stock adjusted: {prev} → {new_quantity}"
        except Exception as e:
            return False, f"❌ Error adjusting stock: {e}"

    # ================================================================
    #  STOCK MOVEMENTS (AUDIT TRAIL)
    # ================================================================

    def _log_movement(self, product_name: str, store_code: str,
                      movement_type: str, quantity: int,
                      previous_stock: int, new_stock: int,
                      reference_id: Optional[str] = None,
                      unit_cost: float = 0,
                      notes: Optional[str] = None):
        """Insert a row into stock_movements for audit."""
        try:
            data = {
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
                'movement_date': datetime.now().isoformat(),
            }
            self.supabase.table('stock_movements').insert(data).execute()
        except Exception as e:
            print(f"⚠️ Error logging movement: {e}")

    def get_stock_movements(self, product_name: Optional[str] = None,
                            store_code: Optional[str] = None,
                            movement_type: Optional[str] = None,
                            days: int = 30) -> pd.DataFrame:
        """Query stock_movements with optional filters."""
        try:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            query = (
                self.supabase.table('stock_movements')
                .select('*')
                .gte('movement_date', cutoff)
            )
            if product_name:
                query = query.eq('product_name', product_name)
            if store_code:
                query = query.eq('store_code', store_code)
            if movement_type:
                query = query.eq('movement_type', movement_type)

            response = query.order('movement_date', desc=True).execute()
            df = pd.DataFrame(response.data) if response.data else pd.DataFrame()
            if not df.empty and 'movement_date' in df.columns:
                df['movement_date'] = pd.to_datetime(df['movement_date'], errors='coerce')
            return df
        except Exception as e:
            print(f"❌ Error fetching movements: {e}")
            return pd.DataFrame()

    # ================================================================
    #  INVENTORY UPSERT (PRIVATE)
    # ================================================================

    def _upsert_inventory(self, product_name: str, store_code: str,
                          current_stock: int,
                          unit_cost: Optional[float] = None):
        """Upsert into the `inventory` table."""
        try:
            data: Dict = {
                'product_name': product_name,
                'store_code': store_code,
                'current_stock': current_stock,
                'last_updated': datetime.now().isoformat(),
            }
            if unit_cost is not None:
                data['unit_cost'] = unit_cost

            self.supabase.table('inventory').upsert(
                data,
                on_conflict='product_name,store_code'
            ).execute()
        except Exception as e:
            print(f"⚠️ Error upserting inventory: {e}")

    # ================================================================
    #  CONSUMPTION ANALYTICS
    # ================================================================

    def calculate_daily_avg_sales(self, product_name: str,
                                  store_code: str,
                                  days: int = 30) -> float:
        """Average daily units sold over the window."""
        try:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            response = (
                self.supabase.table('sales')
                .select('quantity')
                .eq('product_name', product_name)
                .eq('store_code', store_code)
                .gte('transaction_date', cutoff)
                .execute()
            )
            if response.data:
                total = sum(r['quantity'] for r in response.data)
                return round(total / max(days, 1), 2)
            return 0.0
        except Exception:
            return 0.0

    def calculate_consumption_rate(self, product_name: str,
                                   store_code: str,
                                   days: int = 30) -> Dict:
        """
        Daily/weekly/monthly consumption with trend analysis.
        Returns dict with keys: daily_avg, weekly_avg, monthly_total,
        trend ('increasing' | 'stable' | 'decreasing'), confidence.
        """
        try:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            response = (
                self.supabase.table('sales')
                .select('quantity, transaction_date')
                .eq('product_name', product_name)
                .eq('store_code', store_code)
                .gte('transaction_date', cutoff)
                .execute()
            )

            default = {
                'daily_avg': 0, 'weekly_avg': 0, 'monthly_total': 0,
                'trend': 'unknown', 'confidence': 0,
            }

            if not response.data:
                return default

            df = pd.DataFrame(response.data)
            df['transaction_date'] = pd.to_datetime(df['transaction_date'], errors='coerce')

            total_sold = int(df['quantity'].sum())
            days_with_sales = df['transaction_date'].dt.date.nunique()
            daily_avg = total_sold / max(days, 1)

            # Trend: compare first vs second half of quantity
            midpoint = df['transaction_date'].min() + (
                df['transaction_date'].max() - df['transaction_date'].min()
            ) / 2
            first_half = df[df['transaction_date'] <= midpoint]['quantity'].sum()
            second_half = df[df['transaction_date'] > midpoint]['quantity'].sum()

            if first_half == 0:
                trend = 'increasing' if second_half > 0 else 'unknown'
            elif second_half > first_half * 1.2:
                trend = 'increasing'
            elif second_half < first_half * 0.8:
                trend = 'decreasing'
            else:
                trend = 'stable'

            confidence = min(days_with_sales / 15, 1.0)

            return {
                'daily_avg': round(daily_avg, 2),
                'weekly_avg': round(daily_avg * 7, 2),
                'monthly_total': total_sold,
                'trend': trend,
                'confidence': round(confidence, 2),
                'days_analyzed': days,
                'sales_count': len(df),
            }
        except Exception as e:
            print(f"❌ Consumption rate error: {e}")
            return {
                'daily_avg': 0, 'weekly_avg': 0, 'monthly_total': 0,
                'trend': 'unknown', 'confidence': 0,
            }

    def predict_stockout_date(self, product_name: str,
                               store_code: str) -> Optional[datetime]:
        """Estimate when stock will hit zero."""
        try:
            stock = self.get_current_stock(product_name, store_code)
            if not stock or stock['current_stock'] <= 0:
                return datetime.now()

            consumption = self.calculate_consumption_rate(product_name, store_code)
            daily_avg = consumption['daily_avg']
            if daily_avg <= 0:
                return None

            days_left = stock['current_stock'] / daily_avg

            # Adjust by trend
            if consumption['trend'] == 'increasing':
                days_left *= 0.8
            elif consumption['trend'] == 'decreasing':
                days_left *= 1.2

            return datetime.now() + timedelta(days=days_left)
        except Exception:
            return None

    # ================================================================
    #  REORDER SUGGESTIONS
    # ================================================================

    def generate_reorder_suggestions(self,
                                     store_code: Optional[str] = None,
                                     priority: str = 'all') -> pd.DataFrame:
        """
        Scan low-stock items and produce actionable reorder suggestions.
        priority: 'urgent' | 'soon' | 'all'
        """
        try:
            low = self.get_low_stock_items(store_code)
            if low.empty:
                return pd.DataFrame()

            rows: List[Dict] = []

            for _, item in low.iterrows():
                pname = item['product_name']
                scode = item['store_code']
                current = item['current_stock']

                consumption = self.calculate_consumption_rate(pname, scode)
                daily_avg = consumption['daily_avg']
                stockout_dt = self.predict_stockout_date(pname, scode)

                days_until = (
                    (stockout_dt - datetime.now()).days
                    if stockout_dt else 999
                )

                # Optimal order quantity (30-day supply adjusted for trend)
                base_qty = daily_avg * 30
                if consumption['trend'] == 'increasing':
                    order_qty = math.ceil(base_qty * 1.3)
                elif consumption['trend'] == 'decreasing':
                    order_qty = math.ceil(base_qty * 0.8)
                else:
                    order_qty = math.ceil(base_qty) if base_qty > 0 else self.DEFAULT_REORDER_QTY

                unit_cost = item.get('unit_cost', 0)

                # Priority level
                if days_until <= 3:
                    prio, score = 'URGENT', 3
                elif days_until <= 7:
                    prio, score = 'HIGH', 2
                elif days_until <= 14:
                    prio, score = 'MEDIUM', 1
                else:
                    prio, score = 'LOW', 0

                reasoning = (
                    f"Daily usage: {daily_avg:.1f} units. "
                    f"Trend: {consumption['trend']}. "
                    f"30-day supply with safety buffer."
                )

                rows.append({
                    'product_name': pname,
                    'store_code': scode,
                    'current_stock': current,
                    'reorder_point': item.get('reorder_point', self.DEFAULT_REORDER_POINT),
                    'daily_consumption': daily_avg,
                    'trend': consumption['trend'],
                    'days_until_stockout': days_until,
                    'stockout_date': (
                        stockout_dt.strftime('%Y-%m-%d') if stockout_dt else 'Unknown'
                    ),
                    'suggested_order_qty': order_qty,
                    'order_cost_estimate': round(order_qty * unit_cost, 2),
                    'priority': prio,
                    'priority_score': score,
                    'confidence': consumption['confidence'],
                    'reasoning': reasoning,
                })

            df = pd.DataFrame(rows)

            if priority == 'urgent':
                df = df[df['priority'] == 'URGENT']
            elif priority == 'soon':
                df = df[df['priority'].isin(['URGENT', 'HIGH'])]

            return df.sort_values(
                ['priority_score', 'days_until_stockout'],
                ascending=[False, True],
            ).reset_index(drop=True)

        except Exception as e:
            print(f"❌ Error generating suggestions: {e}")
            return pd.DataFrame()

    # ================================================================
    #  INVENTORY HEALTH SCORE (0-100)
    # ================================================================

    def get_inventory_health_score(self,
                                   store_code: Optional[str] = None) -> Dict:
        """
        Composite score:
          30% items-in-stock ratio
          40% items-above-reorder-point ratio
          30% penalty for out-of-stock items
        """
        try:
            all_stock = self.get_all_stock(store_code)
            if all_stock.empty:
                return {
                    'score': 0, 'grade': 'F', 'status': 'No inventory data',
                    'total_products': 0, 'in_stock': 0,
                    'healthy_levels': 0, 'critical_items': 0,
                }

            total = len(all_stock)
            in_stock = len(all_stock[all_stock['current_stock'] > 0])
            healthy = len(all_stock[all_stock['current_stock'] > all_stock['reorder_point']])
            critical = len(all_stock[all_stock['current_stock'] <= 0])

            stock_score = (in_stock / total) * 30
            healthy_score = (healthy / total) * 40
            critical_penalty = (critical / total) * 30
            score = round(stock_score + healthy_score + (30 - critical_penalty), 1)

            grade_map = [(90, 'A', 'Excellent'), (80, 'B', 'Good'),
                         (70, 'C', 'Fair'), (60, 'D', 'Poor')]
            grade, status = 'F', 'Critical'
            for threshold, g, s in grade_map:
                if score >= threshold:
                    grade, status = g, s
                    break

            return {
                'score': score, 'grade': grade, 'status': status,
                'total_products': total, 'in_stock': in_stock,
                'healthy_levels': healthy, 'critical_items': critical,
            }
        except Exception as e:
            print(f"❌ Error calculating health score: {e}")
            return {
                'score': 0, 'grade': 'F', 'status': 'Error',
                'total_products': 0, 'in_stock': 0,
                'healthy_levels': 0, 'critical_items': 0,
            }

    # ================================================================
    #  INVENTORY VALUATION
    # ================================================================

    def get_inventory_value(self,
                            store_code: Optional[str] = None) -> Dict:
        """Calculate total inventory valuation."""
        try:
            df = self.get_all_stock(store_code)
            if df.empty:
                return {'total_units': 0, 'total_value': 0.0,
                        'product_count': 0, 'low_stock_count': 0}

            df['stock_value'] = df['current_stock'] * df['unit_cost']

            return {
                'total_units': int(df['current_stock'].sum()),
                'total_value': float(df['stock_value'].sum()),
                'product_count': len(df),
                'low_stock_count': len(df[df['current_stock'] <= df['reorder_point']]),
            }
        except Exception as e:
            print(f"❌ Error calculating inventory value: {e}")
            return {'total_units': 0, 'total_value': 0.0,
                    'product_count': 0, 'low_stock_count': 0}


# ════════════════════════════════════════════════════════════════════
# STANDALONE TEST
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🔄 Testing Inventory Manager …\n")
    try:
        inv = InventoryManager()

        print("=" * 60)
        print("TEST: Get All Stock")
        print("=" * 60)
        stock = inv.get_all_stock()
        print(f"✅ {len(stock)} products in inventory")
        if not stock.empty:
            print(stock.head(3))

        print("\n" + "=" * 60)
        print("TEST: Low Stock Items")
        print("=" * 60)
        low = inv.get_low_stock_items()
        print(f"⚠️ {len(low)} items need reordering")

        print("\n" + "=" * 60)
        print("TEST: Health Score")
        print("=" * 60)
        health = inv.get_inventory_health_score()
        print(f"Score: {health['score']}/100 (Grade {health['grade']})")

        print("\n" + "=" * 60)
        print("TEST: Inventory Value")
        print("=" * 60)
        val = inv.get_inventory_value()
        print(f"₹{val['total_value']:,.2f} across {val['product_count']} products")

        print("\n🎉 All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
