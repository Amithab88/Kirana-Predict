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
    st.info("👈 Use the **sidebar** on the left to navigate between modules.")

    # Recent Activity Preview
    st.markdown("---")
    st.subheader("📋 Recent Sales Activity")

    if not filtered_home_df.empty:
        st.dataframe(filtered_home_df.head(10), use_container_width=True)
        if len(filtered_home_df) > 10:
            st.caption(f"Showing 10 of {len(filtered_home_df)} records")
    else:
        st.warning("⚠️ No records match your filters")