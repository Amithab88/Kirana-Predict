"""
app/inventory_dashboard.py — Inventory Management Dashboard
============================================================
Real-time inventory tracking, reorder suggestions, analytics,
stock movement history, and settings.

Uses consolidated InventoryManager for all operations
(no separate ReorderEngine / AlertManager needed).
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from core.inventory_manager import InventoryManager
from core.database_manager import KiranaDatabase


def render(db: KiranaDatabase):
    """Render the inventory dashboard page."""

    inventory = InventoryManager()

    st.title("📦 Inventory Management Dashboard")
    st.markdown("---")

    # ── Store Selector ─────────────────────────────────────────────
    stores = db.get_active_stores()

    if stores.empty:
        st.warning("No active stores found. Please add stores in Store Management.")
        return

    store_options = ['All Stores'] + stores['store_code'].tolist()
    selected_store = st.selectbox("Select Store", store_options)
    store_code = None if selected_store == 'All Stores' else selected_store

    st.markdown("---")

    # ── Health Score Card ──────────────────────────────────────────
    health = inventory.get_inventory_health_score(store_code)

    col1, col2, col3, col4, col5 = st.columns(5)

    grade_icon = {
        'A': '🟢', 'B': '🟡', 'C': '🟠', 'D': '🔴', 'F': '⛔'
    }.get(health['grade'], '⚪')

    col1.metric(
        "Health Score",
        f"{health['score']}/100",
        f"{grade_icon} Grade {health['grade']}"
    )
    col2.metric("Total Products", health['total_products'])
    col3.metric("In Stock", health['in_stock'])
    col4.metric("Healthy Levels", health['healthy_levels'])
    col5.metric(
        "Critical Items", health['critical_items'],
        delta=f"-{health['critical_items']}" if health['critical_items'] > 0 else "0",
        delta_color="inverse"
    )

    st.markdown("---")

    # ── Tabs ───────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Current Stock",
        "🔔 Reorder Alerts",
        "📈 Analytics",
        "📜 Stock Movements",
        "⚙️ Settings"
    ])

    # ─────────────────────────────────────────────────────────────
    # TAB 1: CURRENT STOCK
    # ─────────────────────────────────────────────────────────────
    with tab1:
        st.subheader("📊 Current Stock Levels")

        stock_df = inventory.get_all_stock(store_code)

        if not stock_df.empty:
            # Derive status column
            def _status(row):
                if row['current_stock'] <= 0:
                    return '🔴 Out of Stock'
                elif row['current_stock'] <= row['reorder_point']:
                    return '🟡 Low Stock'
                return '🟢 In Stock'

            stock_df['status'] = stock_df.apply(_status, axis=1)
            stock_df['stock_value'] = stock_df['current_stock'] * stock_df['unit_cost']

            # Filters
            fcol1, fcol2 = st.columns(2)
            with fcol1:
                status_filter = st.multiselect(
                    "Filter by Status",
                    options=['🟢 In Stock', '🟡 Low Stock', '🔴 Out of Stock'],
                    default=['🟢 In Stock', '🟡 Low Stock', '🔴 Out of Stock']
                )
            with fcol2:
                search = st.text_input("Search Product", "")

            filtered = stock_df[stock_df['status'].isin(status_filter)]
            if search:
                filtered = filtered[
                    filtered['product_name'].str.contains(search, case=False, na=False)
                ]

            # Table
            display_cols = [
                'product_name', 'store_code', 'current_stock',
                'reorder_point', 'unit_cost', 'stock_value', 'status'
            ]
            # Only show columns that exist
            display_cols = [c for c in display_cols if c in filtered.columns]

            st.dataframe(
                filtered[display_cols].style.format({
                    'unit_cost': '₹{:.2f}',
                    'stock_value': '₹{:,.2f}',
                }),
                use_container_width=True,
                height=400,
            )

            # Summary row
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("Total Stock Value", f"₹{stock_df['stock_value'].sum():,.2f}")
            sc2.metric("Products Shown", len(filtered))
            sc3.metric("Low Stock Items",
                        len(stock_df[stock_df['status'] == '🟡 Low Stock']))
        else:
            st.info("No inventory data available. Stock will appear after sales or purchases are recorded.")

    # ─────────────────────────────────────────────────────────────
    # TAB 2: REORDER ALERTS
    # ─────────────────────────────────────────────────────────────
    with tab2:
        st.subheader("🔔 Reorder Suggestions")

        col_filter, col_action = st.columns([3, 1])
        with col_filter:
            priority_filter = st.selectbox(
                "Priority Level",
                ['All', 'Urgent Only', 'High Priority']
            )

        priority_map = {
            'All': 'all', 'Urgent Only': 'urgent', 'High Priority': 'soon'
        }

        suggestions = inventory.generate_reorder_suggestions(
            store_code=store_code,
            priority=priority_map[priority_filter],
        )

        if not suggestions.empty:
            urgent_count = len(suggestions[suggestions['priority'] == 'URGENT'])
            high_count = len(suggestions[suggestions['priority'] == 'HIGH'])

            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("🚨 Urgent", urgent_count, help="≤3 days stock left")
            mc2.metric("⚡ High Priority", high_count, help="≤7 days stock left")
            mc3.metric("📋 Total Items", len(suggestions))

            st.markdown("---")

            for idx, item in suggestions.iterrows():
                with st.expander(
                    f"{item['priority']} — {item['product_name']} "
                    f"({item['days_until_stockout']} days left)",
                    expanded=(item['priority'] == 'URGENT')
                ):
                    ec1, ec2, ec3, ec4 = st.columns(4)
                    ec1.metric("Current Stock", f"{item['current_stock']} units")
                    ec2.metric("Daily Usage", f"{item['daily_consumption']:.1f} units/day")
                    ec3.metric("Suggested Order", f"{item['suggested_order_qty']} units")
                    ec4.metric("Est. Cost", f"₹{item['order_cost_estimate']:,.2f}")

                    trend_icon = {
                        'increasing': '📈', 'decreasing': '📉', 'stable': '➡️'
                    }.get(item['trend'], '❓')

                    st.write(f"**Trend:** {item['trend'].title()} {trend_icon}")
                    st.write(f"**Stockout Date:** {item['stockout_date']}")
                    st.write(f"**Confidence:** {item['confidence']:.0%}")
                    st.info(f"💡 **Recommendation:** {item['reasoning']}")
        else:
            st.success("✅ All products have sufficient stock levels!")
            st.balloons()

    # ─────────────────────────────────────────────────────────────
    # TAB 3: ANALYTICS
    # ─────────────────────────────────────────────────────────────
    with tab3:
        st.subheader("📈 Inventory Analytics")

        stock_df = inventory.get_all_stock(store_code)

        if not stock_df.empty:
            acol1, acol2 = st.columns(2)

            with acol1:
                st.write("**Stock Status Distribution**")
                status_counts = stock_df.apply(
                    lambda r: 'Out of Stock' if r['current_stock'] <= 0
                    else 'Low Stock' if r['current_stock'] <= r['reorder_point']
                    else 'In Stock',
                    axis=1
                ).value_counts()

                fig_pie = px.pie(
                    values=status_counts.values,
                    names=status_counts.index,
                    color=status_counts.index,
                    color_discrete_map={
                        'In Stock': '#4caf50',
                        'Low Stock': '#ff9800',
                        'Out of Stock': '#f44336',
                    },
                )
                fig_pie.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            with acol2:
                st.write("**Stock Value by Product (Top 10)**")
                stock_df['stock_value'] = stock_df['current_stock'] * stock_df['unit_cost']
                top10 = stock_df.nlargest(10, 'stock_value')

                fig_bar = px.bar(
                    top10, x='stock_value', y='product_name',
                    orientation='h',
                    labels={'stock_value': 'Stock Value (₹)', 'product_name': 'Product'},
                    color_discrete_sequence=['#6C63FF'],
                )
                fig_bar.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                )
                st.plotly_chart(fig_bar, use_container_width=True)

            # Stock vs Reorder Point comparison
            st.write("**Stock Levels vs Reorder Points**")
            comp = stock_df[['product_name', 'current_stock', 'reorder_point']].head(15)

            fig_cmp = go.Figure()
            fig_cmp.add_trace(go.Bar(
                x=comp['product_name'], y=comp['current_stock'],
                name='Current Stock', marker_color='#6C63FF',
            ))
            fig_cmp.add_trace(go.Scatter(
                x=comp['product_name'], y=comp['reorder_point'],
                name='Reorder Point', mode='markers',
                marker=dict(size=10, color='#f44336', symbol='diamond'),
            ))
            fig_cmp.update_layout(
                height=400,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
            )
            st.plotly_chart(fig_cmp, use_container_width=True)

            # Inventory valuation
            val = inventory.get_inventory_value(store_code)
            vcol1, vcol2, vcol3 = st.columns(3)
            vcol1.metric("Total Inventory Value", f"₹{val['total_value']:,.2f}")
            vcol2.metric("Total Units", f"{val['total_units']:,}")
            vcol3.metric("Products Tracked", val['product_count'])
        else:
            st.info("No data available for analytics yet.")

    # ─────────────────────────────────────────────────────────────
    # TAB 4: STOCK MOVEMENTS
    # ─────────────────────────────────────────────────────────────
    with tab4:
        st.subheader("📜 Stock Movement History")

        days = st.slider("Show last N days", 7, 90, 30)

        movements = inventory.get_stock_movements(
            store_code=store_code, days=days,
        )

        if not movements.empty:
            # Summary
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("Total Movements", len(movements))
            mc2.metric("Sales",
                        len(movements[movements['movement_type'] == 'SALE']))
            mc3.metric("Purchases",
                        len(movements[movements['movement_type'] == 'PURCHASE']))
            total_val = movements['total_value'].sum() if 'total_value' in movements.columns else 0
            mc4.metric("Total Value", f"₹{total_val:,.2f}")

            st.markdown("---")

            # Type filter
            all_types = movements['movement_type'].unique().tolist()
            movement_types = st.multiselect(
                "Filter by Type", options=all_types, default=all_types,
            )
            filtered_mv = movements[movements['movement_type'].isin(movement_types)]

            display_mv_cols = [
                'movement_date', 'product_name', 'store_code',
                'movement_type', 'quantity',
            ]
            # Add optional cols if present
            for c in ['previous_stock', 'new_stock', 'total_value']:
                if c in filtered_mv.columns:
                    display_mv_cols.append(c)

            fmt = {}
            if 'total_value' in filtered_mv.columns:
                fmt['total_value'] = '₹{:,.2f}'

            st.dataframe(
                filtered_mv[display_mv_cols]
                .sort_values('movement_date', ascending=False)
                .style.format(fmt),
                use_container_width=True,
                height=400,
            )

            # Daily trend chart
            st.write("**Daily Stock Movements**")
            filtered_mv_copy = filtered_mv.copy()
            filtered_mv_copy['date'] = filtered_mv_copy['movement_date'].dt.date
            daily_mv = filtered_mv_copy.groupby('date').agg(
                quantity=('quantity', 'sum'),
            ).reset_index()

            fig_line = px.line(
                daily_mv, x='date', y='quantity',
                title="Daily Movement Quantity",
                color_discrete_sequence=['#6C63FF'],
            )
            fig_line.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
            )
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("No stock movements recorded yet.")

    # ─────────────────────────────────────────────────────────────
    # TAB 5: SETTINGS
    # ─────────────────────────────────────────────────────────────
    with tab5:
        st.subheader("⚙️ Inventory Settings")

        st.write("**Reorder Settings**")
        rcol1, rcol2 = st.columns(2)
        with rcol1:
            lead_time = st.number_input(
                "Lead Time (days)", min_value=1, max_value=30, value=7
            )
        with rcol2:
            safety_stock = st.number_input(
                "Safety Stock (days)", min_value=1, max_value=30, value=7
            )
        st.info(
            f"💡 Orders will be placed when stock falls below "
            f"{lead_time + safety_stock} days of supply"
        )

        st.markdown("---")

        st.write("**Stock Adjustment**")
        adj_col1, adj_col2 = st.columns(2)

        with adj_col1:
            adj_store = st.selectbox(
                "Store", stores['store_code'].tolist(),
                key="adj_store"
            )
            adj_stock = inventory.get_all_stock(adj_store)
            adj_products = adj_stock['product_name'].tolist() if not adj_stock.empty else []
            adj_product = st.selectbox("Product", adj_products, key="adj_product")

        with adj_col2:
            adj_qty = st.number_input("New Stock Quantity", min_value=0, value=0, key="adj_qty")
            adj_reason = st.text_input("Reason", "Manual adjustment", key="adj_reason")

        if st.button("🔧 Apply Adjustment", type="primary"):
            if adj_product:
                success, msg = inventory.adjust_stock(
                    adj_product, adj_store, adj_qty, adj_reason
                )
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
            else:
                st.warning("Please select a product")


# For standalone testing
if __name__ == "__main__":
    st.set_page_config(page_title="Inventory Dashboard", layout="wide")
    db = KiranaDatabase()
    render(db)