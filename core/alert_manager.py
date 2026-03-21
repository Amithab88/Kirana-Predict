"""
core/alert_manager.py - Email Alert System for Inventory
Sends automated email notifications for low stock alerts
"""

import os
from datetime import datetime
from typing import List, Optional, Dict
import pandas as pd

try:
    from core.reorder_engine import ReorderEngine
    from core.email_manager import EmailAlertManager as EmailManager
except ImportError:
    from .reorder_engine import ReorderEngine
    from .email_manager import EmailAlertManager as EmailManager


class AlertManager:
    """
    Manages automated inventory alerts and notifications
    """
    
    def __init__(self):
        self.reorder_engine = ReorderEngine()
        self.email_manager = EmailManager()
    
    # ============================================
    # EMAIL TEMPLATES
    # ============================================
    
    def _generate_low_stock_email(self, suggestions_df: pd.DataFrame, 
                                  store_code: str) -> str:
        """Generate HTML email for low stock alert"""
        
        urgent_items = suggestions_df[suggestions_df['priority'] == 'URGENT']
        high_items = suggestions_df[suggestions_df['priority'] == 'HIGH']
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: #f44336; color: white; padding: 20px; }}
                .urgent {{ background-color: #ffebee; padding: 15px; margin: 10px 0; }}
                .high {{ background-color: #fff3e0; padding: 15px; margin: 10px 0; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th {{ background-color: #333; color: white; padding: 10px; text-align: left; }}
                td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
                .footer {{ color: #666; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🚨 Low Stock Alert - {store_code}</h1>
                <p>Automated inventory notification from Kirana-Predict</p>
            </div>
            
            <div style="padding: 20px;">
                <h2>Alert Summary</h2>
                <p><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                <p><strong>Store:</strong> {store_code}</p>
                <p><strong>Total Items Needing Reorder:</strong> {len(suggestions_df)}</p>
                <p><strong>Urgent Items:</strong> {len(urgent_items)} (≤3 days stock left)</p>
                <p><strong>High Priority Items:</strong> {len(high_items)} (≤7 days stock left)</p>
        """
        
        # Urgent items section
        if not urgent_items.empty:
            html += """
                <div class="urgent">
                    <h3>⚠️ URGENT - Immediate Action Required</h3>
                    <p>These items will run out within 3 days!</p>
                    <table>
                        <tr>
                            <th>Product</th>
                            <th>Current Stock</th>
                            <th>Days Left</th>
                            <th>Order Qty</th>
                            <th>Est. Cost</th>
                        </tr>
            """
            
            for _, item in urgent_items.iterrows():
                html += f"""
                        <tr>
                            <td><strong>{item['product_name']}</strong></td>
                            <td>{item['current_stock']} units</td>
                            <td>{item['days_until_stockout']} days</td>
                            <td>{item['suggested_order_qty']} units</td>
                            <td>₹{item['order_cost_estimate']:,.2f}</td>
                        </tr>
                """
            
            html += """
                    </table>
                </div>
            """
        
        # High priority items
        if not high_items.empty:
            html += """
                <div class="high">
                    <h3>⚡ High Priority</h3>
                    <p>These items need ordering soon (within 7 days)</p>
                    <table>
                        <tr>
                            <th>Product</th>
                            <th>Current Stock</th>
                            <th>Days Left</th>
                            <th>Order Qty</th>
                        </tr>
            """
            
            for _, item in high_items.iterrows():
                html += f"""
                        <tr>
                            <td>{item['product_name']}</td>
                            <td>{item['current_stock']} units</td>
                            <td>{item['days_until_stockout']} days</td>
                            <td>{item['suggested_order_qty']} units</td>
                        </tr>
                """
            
            html += """
                    </table>
                </div>
            """
        
        # All suggestions table
        html += """
                <h3>Complete Reorder List</h3>
                <table>
                    <tr>
                        <th>Priority</th>
                        <th>Product</th>
                        <th>Stock</th>
                        <th>Daily Use</th>
                        <th>Trend</th>
                        <th>Stockout Date</th>
                        <th>Order Qty</th>
                        <th>Est. Cost</th>
                    </tr>
        """
        
        for _, item in suggestions_df.iterrows():
            priority_color = {
                'URGENT': '#f44336',
                'HIGH': '#ff9800',
                'MEDIUM': '#ffc107',
                'LOW': '#4caf50'
            }.get(item['priority'], '#999')
            
            trend_emoji = {
                'increasing': '📈',
                'decreasing': '📉',
                'stable': '➡️'
            }.get(item['trend'], '❓')
            
            html += f"""
                    <tr>
                        <td style="color: {priority_color}; font-weight: bold;">{item['priority']}</td>
                        <td>{item['product_name']}</td>
                        <td>{item['current_stock']}</td>
                        <td>{item['daily_consumption']:.1f}</td>
                        <td>{trend_emoji} {item['trend'].title()}</td>
                        <td>{item['stockout_date']}</td>
                        <td><strong>{item['suggested_order_qty']}</strong></td>
                        <td>₹{item['order_cost_estimate']:,.2f}</td>
                    </tr>
            """
        
        # Calculate total order cost
        total_cost = suggestions_df['order_cost_estimate'].sum()
        
        html += f"""
                    <tr style="background-color: #f5f5f5; font-weight: bold;">
                        <td colspan="7" style="text-align: right;">TOTAL ESTIMATED ORDER COST:</td>
                        <td>₹{total_cost:,.2f}</td>
                    </tr>
                </table>
                
                <div class="footer">
                    <p>This is an automated alert from Kirana-Predict Inventory Management System.</p>
                    <p>Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>For questions, contact your inventory manager.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _generate_daily_summary_email(self, store_code: str) -> str:
        """Generate daily inventory summary email"""
        
        health = self.reorder_engine.get_inventory_health_score(store_code)
        suggestions = self.reorder_engine.generate_reorder_suggestions(store_code)
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: #2196F3; color: white; padding: 20px; }}
                .score-card {{ background-color: #e3f2fd; padding: 20px; margin: 20px 0; 
                              border-left: 5px solid #2196F3; }}
                .metric {{ display: inline-block; margin: 10px 20px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th {{ background-color: #333; color: white; padding: 10px; }}
                td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 Daily Inventory Report - {store_code}</h1>
                <p>{datetime.now().strftime('%A, %B %d, %Y')}</p>
            </div>
            
            <div style="padding: 20px;">
                <div class="score-card">
                    <h2>Inventory Health Score</h2>
                    <h1 style="color: #2196F3; margin: 0;">{health['score']}/100</h1>
                    <h3>Grade: {health['grade']} - {health['status']}</h3>
                    
                    <div class="metric">
                        <strong>Total Products:</strong> {health['total_products']}
                    </div>
                    <div class="metric">
                        <strong>In Stock:</strong> {health['in_stock']}
                    </div>
                    <div class="metric">
                        <strong>Healthy Levels:</strong> {health['healthy_levels']}
                    </div>
                    <div class="metric">
                        <strong>Critical Items:</strong> {health['critical_items']}
                    </div>
                </div>
                
                <h2>Action Items</h2>
                <p><strong>{len(suggestions)}</strong> products need reordering</p>
        """
        
        if not suggestions.empty:
            urgent = len(suggestions[suggestions['priority'] == 'URGENT'])
            if urgent > 0:
                html += f'<p style="color: #f44336;"><strong>⚠️ {urgent} URGENT items need immediate attention!</strong></p>'
            
            html += """
                <table>
                    <tr>
                        <th>Product</th>
                        <th>Stock</th>
                        <th>Priority</th>
                        <th>Days Left</th>
                    </tr>
            """
            
            for _, item in suggestions.head(10).iterrows():
                html += f"""
                    <tr>
                        <td>{item['product_name']}</td>
                        <td>{item['current_stock']}</td>
                        <td>{item['priority']}</td>
                        <td>{item['days_until_stockout']}</td>
                    </tr>
                """
            
            html += "</table>"
        else:
            html += '<p style="color: #4caf50;">✅ All products have sufficient stock levels!</p>'
        
        html += """
                <p style="margin-top: 30px; color: #666; font-size: 12px;">
                    This is an automated daily summary from Kirana-Predict.
                </p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    # ============================================
    # SEND ALERTS
    # ============================================
    
    def send_low_stock_alert(self, store_code: str, 
                            recipients: Optional[List[str]] = None) -> bool:
        """Send low stock alert email"""
        try:
            # Generate reorder suggestions
            suggestions = self.reorder_engine.generate_reorder_suggestions(
                store_code=store_code,
                priority='soon'  # Urgent + High priority only
            )
            
            if suggestions.empty:
                print(f"ℹ️  No low stock alerts for {store_code}")
                return False
            
            # Generate email
            subject = f"🚨 Low Stock Alert - {store_code} - {len(suggestions)} Items Need Reordering"
            html_content = self._generate_low_stock_email(suggestions, store_code)
            
            # Send email
            if recipients is None:
                recipients = os.getenv('EMAIL_RECIPIENTS', '').split(',')
            
            success = self.email_manager.send_email(
                to_email=recipients,
                subject=subject,
                body=html_content,
                is_html=True
            )
            
            if success:
                print(f"✅ Low stock alert sent for {store_code}")
            else:
                print(f"❌ Failed to send alert for {store_code}")
            
            return success
            
        except Exception as e:
            print(f"❌ Error sending low stock alert: {e}")
            return False
    
    def send_daily_summary(self, store_code: str,
                          recipients: Optional[List[str]] = None) -> bool:
        """Send daily inventory summary email"""
        try:
            subject = f"📊 Daily Inventory Report - {store_code} - {datetime.now().strftime('%Y-%m-%d')}"
            html_content = self._generate_daily_summary_email(store_code)
            
            if recipients is None:
                recipients = os.getenv('EMAIL_RECIPIENTS', '').split(',')
            
            success = self.email_manager.send_email(
                to_email=recipients,
                subject=subject,
                body=html_content,
                is_html=True
            )
            
            if success:
                print(f"✅ Daily summary sent for {store_code}")
            else:
                print(f"❌ Failed to send summary for {store_code}")
            
            return success
            
        except Exception as e:
            print(f"❌ Error sending daily summary: {e}")
            return False
    
    def send_alerts_for_all_stores(self) -> Dict[str, bool]:
        """Send low stock alerts for all active stores"""
        try:
            from core.database_manager import KiranaDatabase
            db = KiranaDatabase()
            
            stores = db.get_active_stores()
            results = {}
            
            for _, store in stores.iterrows():
                store_code = store['store_code']
                success = self.send_low_stock_alert(store_code)
                results[store_code] = success
            
            return results
            
        except Exception as e:
            print(f"❌ Error sending alerts for all stores: {e}")
            return {}


# ========================================
# TESTING
# ========================================

if __name__ == "__main__":
    print("🔄 Testing Alert Manager...\n")
    
    try:
        alerts = AlertManager()
        
        print("=" * 60)
        print("TEST: Generate Low Stock Email")
        print("=" * 60)
        
        # Generate suggestions for testing
        suggestions = alerts.reorder_engine.generate_reorder_suggestions('STORE001')
        
        if not suggestions.empty:
            html = alerts._generate_low_stock_email(suggestions, 'STORE001')
            print(f"✅ Email generated ({len(html)} characters)")
            print("\nPreview (first 500 chars):")
            print(html[:500] + "...")
        else:
            print("ℹ️  No low stock items to alert about")
        
        print("\n🎉 Test Passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
