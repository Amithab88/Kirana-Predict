"""
app/store_management_page.py – Multi-Store Management page (Admin only).
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import time
from core.database_manager import KiranaDatabase


def render(db: KiranaDatabase):
    st.title("🏪 Multi-Store Management")
    st.markdown("---")

    # ── Summary cards ──────────────────────────────────────────────────────
    stores_df = db.get_all_stores()
    store_perf = db.get_store_performance()
    active_stores = pd.DataFrame()

    if not stores_df.empty:
        col1, col2, col3, col4 = st.columns(4)
        active_stores = stores_df[stores_df['is_active'] == True]
        col1.metric("Total Stores", len(stores_df))
        col2.metric("Active Stores", len(active_stores))

        if not store_perf.empty:
            col3.metric("Total Revenue", f"₹{store_perf['total_revenue'].sum():,.0f}")
            best_store = store_perf.iloc[0]['store_name'] if len(store_perf) > 0 else "N/A"
            col4.metric("Top Performer", best_store)

    st.markdown("---")

    # ── Tabs ───────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 All Stores",
        "➕ Add New Store",
        "📊 Store Performance",
        "🔄 Store Comparison"
    ])

    # TAB 1: ALL STORES
    with tab1:
        st.subheader("📋 All Stores")

        if not stores_df.empty:
            for idx, store in stores_df.iterrows():
                with st.expander(
                    f"{'🟢' if store['is_active'] else '🔴'} {store['store_name']} ({store['store_code']})",
                    expanded=False
                ):
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.write(f"**Location:** {store['city']}, {store['state']}")
                        st.write(f"**Address:** {store.get('address', 'N/A')}")
                        st.write(f"**Store Code:** {store['store_code']}")
                        st.write(f"**Status:** {'✅ Active' if store['is_active'] else '❌ Inactive'}")
                        if store.get('pos_system'):
                            st.write(f"**POS System:** {store['pos_system']}")

                    with col2:
                        if not store_perf.empty:
                            perf = store_perf[store_perf['store_code'] == store['store_code']]
                            if not perf.empty:
                                st.metric("Revenue", f"₹{perf.iloc[0]['total_revenue']:,.0f}")
                                st.metric("Transactions", f"{perf.iloc[0]['total_transactions']:,}")

                    col_a, col_b, col_c = st.columns(3)

                    with col_a:
                        if st.button("View Details", key=f"view_{store['store_code']}"):
                            st.session_state['selected_store'] = store['store_code']
                            st.session_state.page = 'Store Details'
                            st.rerun()

                    with col_b:
                        new_status = not store['is_active']
                        status_text = "Activate" if new_status else "Deactivate"
                        if st.button(status_text, key=f"toggle_{store['store_code']}"):
                            if db.update_store(store['store_code'], {'is_active': new_status}):
                                st.success(f"Store {status_text}d!")
                                st.rerun()

                    with col_c:
                        if st.button("Edit", key=f"edit_{store['store_code']}", type="primary"):
                            st.session_state['edit_store'] = store['store_code']
                            st.rerun()

                    # Inline edit form
                    if st.session_state.get('edit_store') == store['store_code']:
                        st.markdown("---")
                        st.subheader("✏️ Edit Store")
                        with st.form(f"edit_form_{store['store_code']}"):
                            new_name = st.text_input("Store Name", value=store['store_name'])
                            new_city = st.text_input("City", value=store['city'])
                            new_state = st.text_input("State", value=store['state'])
                            new_address = st.text_area("Address", value=store.get('address', ''))
                            new_pos = st.text_input("POS System", value=store.get('pos_system', ''))

                            col_save, col_cancel = st.columns(2)
                            with col_save:
                                if st.form_submit_button("💾 Save Changes", type="primary"):
                                    update_data = {
                                        'store_name': new_name,
                                        'city': new_city,
                                        'state': new_state,
                                        'address': new_address,
                                        'pos_system': new_pos
                                    }
                                    if db.update_store(store['store_code'], update_data):
                                        st.success("✅ Store updated successfully!")
                                        st.session_state['edit_store'] = None
                                        st.rerun()
                            with col_cancel:
                                if st.form_submit_button("❌ Cancel"):
                                    st.session_state['edit_store'] = None
                                    st.rerun()
        else:
            st.info("No stores found. Add your first store in the 'Add New Store' tab!")

    # TAB 2: ADD NEW STORE
    with tab2:
        st.subheader("➕ Add New Store")
        with st.form("add_store_form"):
            st.write("Enter new store details:")
            col1, col2 = st.columns(2)

            with col1:
                store_code = st.text_input("Store Code *", placeholder="e.g., STORE005",
                                           help="Unique identifier (e.g., STORE005)")
                store_name = st.text_input("Store Name *", placeholder="e.g., Chennai Branch")
                city = st.text_input("City *", placeholder="e.g., Chennai")

            with col2:
                state = st.text_input("State *", placeholder="e.g., Tamil Nadu")
                pos_system = st.text_input("POS System", placeholder="e.g., Petpooja, Square, Custom")
                is_active = st.checkbox("Active Store", value=True)

            address = st.text_area("Address", placeholder="Full store address")
            submitted = st.form_submit_button("➕ Add Store", type="primary")

            if submitted:
                if not store_code or not store_name or not city or not state:
                    st.error("❌ Please fill all required fields (marked with *)")
                elif len(stores_df[stores_df['store_code'] == store_code]) > 0:
                    st.error(f"❌ Store code '{store_code}' already exists!")
                else:
                    new_store = {
                        'store_code': store_code.upper(),
                        'store_name': store_name,
                        'city': city,
                        'state': state,
                        'address': address,
                        'pos_system': pos_system if pos_system else None,
                        'is_active': is_active
                    }
                    if db.add_store(new_store):
                        st.success(f"✅ Store '{store_name}' added successfully!")
                        st.balloons()
                        time.sleep(2)
                        st.rerun()

    # TAB 3: STORE PERFORMANCE
    with tab3:
        st.subheader("📊 Store Performance Dashboard")

        if not store_perf.empty:
            st.dataframe(
                store_perf[[
                    'store_name', 'city', 'state',
                    'total_revenue', 'total_transactions',
                    'total_quantity', 'avg_transaction_value'
                ]].style.format({
                    'total_revenue': '₹{:,.0f}',
                    'total_transactions': '{:,}',
                    'total_quantity': '{:,}',
                    'avg_transaction_value': '₹{:,.2f}'
                }),
                use_container_width=True
            )

            st.markdown("---")
            st.subheader("💰 Revenue by Store")
            fig_revenue = px.bar(
                store_perf, x='store_name', y='total_revenue', color='city',
                title="Total Revenue by Store",
                labels={'total_revenue': 'Revenue (₹)', 'store_name': 'Store'}
            )
            st.plotly_chart(fig_revenue, use_container_width=True)

            st.markdown("---")
            st.subheader("📦 Transaction Volume")
            fig_trans = px.bar(
                store_perf, x='store_name', y='total_transactions',
                title="Total Transactions by Store",
                labels={'total_transactions': 'Transactions', 'store_name': 'Store'}
            )
            st.plotly_chart(fig_trans, use_container_width=True)
        else:
            st.info("No sales data available for performance analysis.")

    # TAB 4: STORE COMPARISON
    with tab4:
        st.subheader("🔄 Compare Stores")

        if len(active_stores) >= 2:
            store_options = active_stores['store_name'].tolist()
            selected_stores = st.multiselect(
                "Select 2-4 stores to compare:",
                options=store_options,
                default=store_options[:2] if len(store_options) >= 2 else store_options
            )

            if len(selected_stores) >= 2:
                selected_codes = active_stores[
                    active_stores['store_name'].isin(selected_stores)
                ]['store_code'].tolist()

                comparison_data = []
                for code in selected_codes:
                    store_sales = db.get_sales_by_store(code)
                    if not store_sales.empty:
                        comparison_data.append({
                            'store_code': code,
                            'store_name': active_stores[active_stores['store_code'] == code].iloc[0]['store_name'],
                            'total_revenue': store_sales['total_amount'].sum(),
                            'total_quantity': store_sales['quantity'].sum(),
                            'transactions': len(store_sales),
                            'unique_products': store_sales['product_name'].nunique()
                        })

                if comparison_data:
                    comp_df = pd.DataFrame(comparison_data)
                    cols = st.columns(len(selected_stores))
                    for idx, row in comp_df.iterrows():
                        with cols[idx]:
                            st.metric(row['store_name'], f"₹{row['total_revenue']:,.0f}")
                            st.write(f"📦 {row['transactions']:,} transactions")
                            st.write(f"🛍️ {row['unique_products']} products")

                    st.markdown("---")
                    fig_comp = px.bar(
                        comp_df, x='store_name',
                        y=['total_revenue', 'total_quantity'],
                        barmode='group',
                        title="Revenue & Quantity Comparison"
                    )
                    st.plotly_chart(fig_comp, use_container_width=True)
            else:
                st.info("Please select at least 2 stores to compare.")
        else:
            st.warning("You need at least 2 active stores to use this feature.")


def render_store_details(db: KiranaDatabase):
    """Render the drill-down page for a single store."""
    if 'selected_store' not in st.session_state:
        st.warning("No store selected!")
        if st.button("← Back to Store Management"):
            st.session_state.page = 'Store Management'
            st.rerun()
        return

    store_code = st.session_state['selected_store']
    store = db.get_store_by_code(store_code)

    if not store:
        st.error("Store not found!")
        return

    col1, col2 = st.columns([3, 1])
    with col1:
        st.title(f"🏪 {store['store_name']}")
        st.caption(f"{store['city']}, {store['state']}")
    with col2:
        if st.button("← Back"):
            st.session_state.page = 'Store Management'
            st.rerun()

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("Store Code", store['store_code'])
    col2.metric("Status", "✅ Active" if store['is_active'] else "❌ Inactive")
    col3.metric("POS System", store.get('pos_system', 'N/A'))
    st.markdown("---")

    store_sales = db.get_sales_by_store(store_code)

    if not store_sales.empty:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Revenue", f"₹{store_sales['total_amount'].sum():,.0f}")
        col2.metric("Transactions", f"{len(store_sales):,}")
        col3.metric("Units Sold", f"{store_sales['quantity'].sum():,}")
        col4.metric("Avg Transaction", f"₹{store_sales['total_amount'].mean():,.2f}")
        st.markdown("---")

        tab1, tab2, tab3 = st.tabs(["📈 Sales Trend", "🏆 Top Products", "📊 Detailed Data"])

        with tab1:
            st.subheader("30-Day Sales Trend")
            trend = db.get_store_sales_trend(store_code, days=30)
            if not trend.empty:
                fig = px.line(trend, x='date', y='revenue', title="Daily Revenue",
                              labels={'revenue': 'Revenue (₹)', 'date': 'Date'})
                st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.subheader("Top 10 Products")
            top_products = db.get_store_product_performance(store_code).head(10)
            if not top_products.empty:
                fig = px.bar(top_products, x='product_name', y='revenue',
                             title="Revenue by Product", labels={'revenue': 'Revenue (₹)'})
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(
                    top_products.style.format({
                        'revenue': '₹{:,.0f}',
                        'quantity_sold': '{:,}',
                        'transactions': '{:,}'
                    }),
                    use_container_width=True
                )

        with tab3:
            st.subheader("All Transactions")
            st.dataframe(
                store_sales.sort_values('transaction_date', ascending=False),
                use_container_width=True
            )
            csv = store_sales.to_csv(index=False)
            st.download_button(
                "📥 Download Store Data (CSV)", csv,
                file_name=f"{store_code}_sales_data.csv", mime="text/csv"
            )
    else:
        st.info(f"No sales data available for {store['store_name']} yet.")