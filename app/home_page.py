"""
app/home_page.py – Home hub page with metrics, search, and module navigation.
"""
import streamlit as st
import pandas as pd
from app.utils import export_to_csv, export_to_excel


def render(df: pd.DataFrame, ch_page):
    st.title("📦 Kirana-Predict Central")
    st.markdown("---")

    # Summary Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Products", df['product_name'].nunique())
    c2.metric("Total Sales Volume", f"{df['quantity'].sum():,}")
    c3.metric("Last Update", df['transaction_date'].max().strftime('%d %b %Y'))

    # Export buttons for full sales data
    st.markdown("---")
    col_export1, col_export2, col_export3 = st.columns([1, 1, 2])

    with col_export1:
        csv_data, csv_filename = export_to_csv(df, "all_sales_data")
        st.download_button(
            label="📥 Download All Sales (CSV)",
            data=csv_data,
            file_name=csv_filename,
            mime="text/csv",
            use_container_width=True
        )

    with col_export2:
        excel_data, excel_filename = export_to_excel(df, "all_sales_data")
        st.download_button(
            label="📊 Download All Sales (Excel)",
            data=excel_data,
            file_name=excel_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    # Search & Filter Section
    st.markdown("---")
    st.subheader("🔍 Search & Filter Data")

    filter_col1, filter_col2, filter_col3 = st.columns(3)

    with filter_col1:
        search_query = st.text_input(
            "🔎 Search Product",
            placeholder="Type product name...",
            help="Search by product name"
        )

    with filter_col2:
        all_stores = ['All Stores'] + sorted(df['store_name'].dropna().unique().tolist())
        selected_store = st.selectbox("🏪 Filter by Store", all_stores)

    with filter_col3:
        all_sources = ['All Sources'] + sorted(df['data_source'].dropna().unique().tolist())
        selected_source = st.selectbox("📊 Filter by Data Source", all_sources)

    filtered_home_df = df.copy()

    if search_query:
        filtered_home_df = filtered_home_df[
            filtered_home_df['product_name'].str.contains(search_query, case=False, na=False)
        ]

    if selected_store != 'All Stores':
        filtered_home_df = filtered_home_df[filtered_home_df['store_name'] == selected_store]

    if selected_source != 'All Sources':
        filtered_home_df = filtered_home_df[filtered_home_df['data_source'] == selected_source]

    if search_query or selected_store != 'All Stores' or selected_source != 'All Sources':
        st.info(f"🔍 Showing **{len(filtered_home_df)}** records (filtered from {len(df)} total)")

    st.markdown("---")
    st.markdown("### 🚀 Select a Module:")

    col1, col2 = st.columns(2)
    role = st.session_state.user_role

    with col1:
        if role == 'Admin':
            st.subheader("📊 Sales Analytics")
            st.info("📈 View top-selling products and trends.")
            if st.button("Open Sales Analysis", use_container_width=True, type="primary", key="btn_sales"):
                ch_page('Sales Analysis')
                st.rerun()

            st.subheader("📈 Advanced Analytics")
            st.success("🔥 Deep insights with visual analytics.")
            if st.button("Open Advanced Analytics", use_container_width=True, type="primary", key="btn_analytics"):
                ch_page('Advanced Analytics')
                st.rerun()
        else:
            st.subheader("➕ Add New Sale")
            st.info("Manual Entry for missing stock")
            if st.button("Open Manual Entry", use_container_width=True, type="primary", key="btn_add_sale"):
                ch_page('Add Sale')
                st.rerun()

    with col2:
        st.subheader("🔮 AI Forecasting")
        st.warning("🤖 Predict future demand with ML.")
        if st.button("Open Inventory Forecast", use_container_width=True, type="primary", key="btn_forecast"):
            ch_page('Inventory Forecast')
            st.rerun()

        if role == 'Admin':
            st.subheader("⚖️ Product Comparison")
            st.info("📊 Compare 2-4 products side-by-side.")
            if st.button("Open Product Comparison", use_container_width=True, type="primary", key="btn_comparison"):
                ch_page('Product Comparison')
                st.rerun()

    # Row 3: Alerts & Store Management (Admin only)
    if role == 'Admin':
        row3_col1, row3_col2 = st.columns(2)

        with row3_col1:
            st.subheader("📧 Alert Settings")
            st.error("⚙️ Configure email notifications.")
            if st.button("Open Alert Settings", use_container_width=True, type="primary", key="btn_alerts"):
                ch_page('Alert Settings')
                st.rerun()

        with row3_col2:
            st.subheader("🏪 Store Management")
            st.warning("📍 Manage multiple locations.")
            if st.button("Open Store Management", use_container_width=True, type="primary", key="btn_stores"):
                ch_page('Store Management')
                st.rerun()
        # Row 4: Inventory Dashboard (Admin only)
    if role == 'Admin':
        row4_col1, row4_col2 = st.columns(2)
        
        with row4_col1:
            st.subheader("📦 Inventory Dashboard")
            st.success("📊 Real-time stock tracking & reorder alerts.")
            if st.button("Open Inventory Dashboard", use_container_width=True, type="primary", key="btn_inventory"):
                ch_page('Inventory Dashboard')
                st.rerun()
    else:
        st.info("🔒 Contact your Admin to access Alert Settings or Store Management.")

    # Recent Activity Preview
    st.markdown("---")
    st.subheader("📋 Recent Sales Activity")

    if not filtered_home_df.empty:
        st.dataframe(filtered_home_df.head(10), use_container_width=True)
        if len(filtered_home_df) > 10:
            st.caption(f"Showing 10 of {len(filtered_home_df)} records")
    else:
        st.warning("⚠️ No records match your filters")
