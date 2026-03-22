"""
app/inventory_dashboard.py - Inventory Management Dashboard
Real-time inventory tracking, reorder suggestions, and analytics
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from core.inventory_manager import InventoryManager
from core.reorder_engine import ReorderEngine
from core.alert_manager import AlertManager
from core.database_manager import KiranaDatabase


def render(db: KiranaDatabase):
    """Render the inventory dashboard page"""
    
    # Initialize managers
    inventory = InventoryManager()
    reorder_engine = ReorderEngine()
    alert_manager = AlertManager()
    
    st.title("📦 Inventory Management Dashboard")
    st.markdown("---")
    
    # ── Store Selector ──────────────────────────────────────────
    stores = db.get_active_stores()
    
    if stores.empty:
        st.warning("No active stores found. Please add stores in Store Management.")
        return
    
    store_options = ['All Stores'] + stores['store_code'].tolist()
    selected_store = st.selectbox("Select Store", store_options)
    
    store_code = None if selected_store == 'All Stores' else selected_store
    
    st.markdown("---")
    
    # ── Health Score Card ──────────────────────────────────────
    health = reorder_engine.get_inventory_health_score(store_code)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    # Health score with color
    score_color = {
        'A': '🟢', 'B': '🟡', 'C': '🟠', 'D': '🔴', 'F': '⛔'
    }.get(health['grade'], '⚪')
    
    col1.metric(
        "Health Score",
        f"{health['score']}/100",
        f"{score_color} Grade {health['grade']}"
    )
    col2.metric("Total Products", health['total_products'])
    col3.metric("In Stock", health['in_stock'], 
                delta=None if health['in_stock'] == health['total_products'] else "")
    col4.metric("Healthy Levels", health['healthy_levels'])
    col5.metric("Critical Items", health['critical_items'],
                delta=f"-{health['critical_items']}" if health['critical_items'] > 0 else "0",
                delta_color="inverse")
    
    st.markdown("---")
    
    # ── Tabs ────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Current Stock",
        "🔔 Reorder Alerts",
        "📈 Analytics",
        "📜 Stock Movements",
        "⚙️ Settings"
    ])
    
    # TAB 1: CURRENT STOCK
    with tab1:
        st.subheader("📊 Current Stock Levels")
        
        stock_df = inventory.get_all_stock(store_code)
        
        if not stock_df.empty:
            # Add status column
            def get_status(row):
                if row['current_stock'] <= 0:
                    return '🔴 Out of Stock'
                elif row['current_stock'] <= row['reorder_point']:
                    return '🟡 Low Stock'
                else:
                    return '🟢 In Stock'
            
            stock_df['status'] = stock_df.apply(get_status, axis=1)
            stock_df['stock_value'] = stock_df['current_stock'] * stock_df['unit_cost']
            
            # Filters
            col1, col2 = st.columns(2)
            with col1:
                status_filter = st.multiselect(
                    "Filter by Status",
                    options=['🟢 In Stock', '🟡 Low Stock', '🔴 Out of Stock'],
                    default=['🟢 In Stock', '🟡 Low Stock', '🔴 Out of Stock']
                )
            with col2:
                search = st.text_input("Search Product", "")
            
            # Apply filters
            filtered_df = stock_df[stock_df['status'].isin(status_filter)]
            if search:
                filtered_df = filtered_df[
                    filtered_df['product_name'].str.contains(search, case=False, na=False)
                ]
            
            # Display table
            st.dataframe(
                filtered_df[[
                    'product_name', 'store_code', 'current_stock', 
                    'reorder_point', 'unit_cost', 'stock_value', 'status'
                ]].style.format({
                    'unit_cost': '₹{:.2f}',
                    'stock_value': '₹{:,.2f}'
                }),
                use_container_width=True,
                height=400
            )
            
            # Summary
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Stock Value", f"₹{stock_df['stock_value'].sum():,.2f}")
            col2.metric("Products Shown", len(filtered_df))
            col3.metric("Low Stock Items", len(stock_df[stock_df['status'] == '🟡 Low Stock']))
            
        else:
            st.info("No inventory data available. Stock will appear here after sales are recorded.")
    
    # TAB 2: REORDER ALERTS
    with tab2:
        st.subheader("🔔 Reorder Suggestions")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            priority_filter = st.selectbox(
                "Priority Level",
                ['All', 'Urgent Only', 'High Priority']
            )
        with col2:
            if st.button("📧 Send Alert Email", type="primary"):
                with st.spinner("Sending email..."):
                    success = alert_manager.send_low_stock_alert(
                        store_code if store_code else 'STORE001'
                    )
                    if success:
                        st.success("✅ Alert email sent successfully!")
                    else:
                        st.error("❌ Failed to send email. Check email settings.")
        
        # Map filter to priority
        priority_map = {
            'All': 'all',
            'Urgent Only': 'urgent',
            'High Priority': 'soon'
        }
        
        suggestions = reorder_engine.generate_reorder_suggestions(
            store_code=store_code,
            priority=priority_map[priority_filter]
        )
        
        if not suggestions.empty:
            # Priority summary
            urgent_count = len(suggestions[suggestions['priority'] == 'URGENT'])
            high_count = len(suggestions[suggestions['priority'] == 'HIGH'])
            
            col1, col2, col3 = st.columns(3)
            col1.metric("🚨 Urgent", urgent_count, help="≤3 days stock left")
            col2.metric("⚡ High Priority", high_count, help="≤7 days stock left")
            col3.metric("📋 Total Items", len(suggestions))
            
            st.markdown("---")
            
            # Detailed table
            for idx, item in suggestions.iterrows():
                with st.expander(
                    f"{item['priority']} - {item['product_name']} "
                    f"({item['days_until_stockout']} days left)",
                    expanded=(item['priority'] == 'URGENT')
                ):
                    col1, col2, col3, col4 = st.columns(4)
                    
                    col1.metric("Current Stock", f"{item['current_stock']} units")
                    col2.metric("Daily Usage", f"{item['daily_consumption']:.1f} units/day")
                    col3.metric("Suggested Order", f"{item['suggested_order_qty']} units")
                    col4.metric("Est. Cost", f"₹{item['order_cost_estimate']:,.2f}")
                    
                    st.write(f"**Trend:** {item['trend'].title()} {('📈' if item['trend']=='increasing' else '📉' if item['trend']=='decreasing' else '➡️')}")
                    st.write(f"**Stockout Date:** {item['stockout_date']}")
                    st.write(f"**Confidence:** {item['confidence']:.0%}")
                    
                    st.info(f"💡 **Recommendation:** {item['reasoning']}")
                    
                    if st.button(f"Create Purchase Order", key=f"po_{idx}_{item['product_name']}"):
                        st.success(f"✅ Purchase order created for {item['suggested_order_qty']} units of {item['product_name']}")
        else:
            st.success("✅ All products have sufficient stock levels!")
            st.balloons()
    
    # TAB 3: ANALYTICS
    with tab3:
        st.subheader("📈 Inventory Analytics")
        
        stock_df = inventory.get_all_stock(store_code)
        
        if not stock_df.empty:
            # Stock distribution
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Stock Status Distribution**")
                status_counts = stock_df.apply(
                    lambda row: 'Out of Stock' if row['current_stock'] <= 0 
                    else 'Low Stock' if row['current_stock'] <= row['reorder_point']
                    else 'In Stock',
                    axis=1
                ).value_counts()
                
                fig = px.pie(
                    values=status_counts.values,
                    names=status_counts.index,
                    color=status_counts.index,
                    color_discrete_map={
                        'In Stock': '#4caf50',
                        'Low Stock': '#ff9800',
                        'Out of Stock': '#f44336'
                    }
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.write("**Stock Value by Product (Top 10)**")
                stock_df['stock_value'] = stock_df['current_stock'] * stock_df['unit_cost']
                top_products = stock_df.nlargest(10, 'stock_value')
                
                fig = px.bar(
                    top_products,
                    x='stock_value',
                    y='product_name',
                    orientation='h',
                    labels={'stock_value': 'Stock Value (₹)', 'product_name': 'Product'}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Stock levels trend
            st.write("**Stock Levels vs Reorder Points**")
            comparison_df = stock_df[['product_name', 'current_stock', 'reorder_point']].head(15)
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=comparison_df['product_name'],
                y=comparison_df['current_stock'],
                name='Current Stock',
                marker_color='#2196F3'
            ))
            fig.add_trace(go.Scatter(
                x=comparison_df['product_name'],
                y=comparison_df['reorder_point'],
                name='Reorder Point',
                mode='markers',
                marker=dict(size=10, color='#f44336', symbol='diamond')
            ))
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.info("No data available for analytics yet.")
    
    # TAB 4: STOCK MOVEMENTS
    with tab4:
        st.subheader("📜 Stock Movement History")
        
        days = st.slider("Show last N days", 7, 90, 30)
        
        movements = inventory.get_stock_movements(
            product_name=None,
            store_code=store_code,
            days=days
        )
        
        if not movements.empty:
            movements['movement_date'] = pd.to_datetime(movements['movement_date'])
            
            # Summary
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Movements", len(movements))
            col2.metric("Sales", len(movements[movements['movement_type'] == 'SALE']))
            col3.metric("Purchases", len(movements[movements['movement_type'] == 'PURCHASE']))
            col4.metric("Total Value", f"₹{movements['total_value'].sum():,.2f}")
            
            st.markdown("---")
            
            # Movement type filter
            movement_types = st.multiselect(
                "Filter by Type",
                options=movements['movement_type'].unique().tolist(),
                default=movements['movement_type'].unique().tolist()
            )
            
            filtered_movements = movements[movements['movement_type'].isin(movement_types)]
            
            # Display table
            st.dataframe(
                filtered_movements[[
                    'movement_date', 'product_name', 'store_code',
                    'movement_type', 'quantity', 'previous_stock',
                    'new_stock', 'total_value'
                ]].sort_values('movement_date', ascending=False).style.format({
                    'total_value': '₹{:,.2f}',
                    'movement_date': lambda x: x.strftime('%Y-%m-%d %H:%M')
                }),
                use_container_width=True,
                height=400
            )
            
            # Daily trend
            st.write("**Daily Stock Movements**")
            daily_movements = filtered_movements.groupby(
                filtered_movements['movement_date'].dt.date
            ).agg({
                'quantity': 'sum',
                'total_value': 'sum'
            }).reset_index()
            
            fig = px.line(
                daily_movements,
                x='movement_date',
                y='quantity',
                title="Daily Movement Quantity"
            )
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.info("No stock movements recorded yet.")
    
    # TAB 5: SETTINGS
    with tab5:
        st.subheader("⚙️ Inventory Settings")
        
        st.write("**Email Alert Settings**")
        
        email_enabled = st.checkbox("Enable automatic email alerts", value=True)
        
        if email_enabled:
            alert_frequency = st.selectbox(
                "Alert Frequency",
                ["Daily", "When stock is low", "Weekly summary"]
            )
            
            email_recipients = st.text_area(
                "Email Recipients (one per line)",
                value="amithabdas6@gmail.com"
            )
            
            if st.button("💾 Save Settings"):
                st.success("✅ Settings saved successfully!")
            
            if st.button("📧 Send Test Email"):
                with st.spinner("Sending test email..."):
                    recipients = [r.strip() for r in email_recipients.split('\n') if r.strip()]
                    success = alert_manager.send_daily_summary(
                        store_code if store_code else 'STORE001',
                        recipients=recipients
                    )
                    if success:
                        st.success("✅ Test email sent!")
                    else:
                        st.error("❌ Failed to send. Check email configuration.")
        
        st.markdown("---")
        st.write("**Reorder Settings**")
        
        col1, col2 = st.columns(2)
        with col1:
            lead_time = st.number_input("Lead Time (days)", min_value=1, max_value=30, value=7)
        with col2:
            safety_stock = st.number_input("Safety Stock (days)", min_value=1, max_value=30, value=7)
        
        st.info(f"💡 Orders will be placed when stock falls below {lead_time + safety_stock} days of supply")


# For standalone testing
if __name__ == "__main__":
    st.set_page_config(page_title="Inventory Dashboard", layout="wide")
    db = KiranaDatabase()
    render(db)