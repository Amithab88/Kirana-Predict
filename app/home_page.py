"""
app/home_page.py – Home dashboard with KPI metrics, quick actions, and recent activity.
"""
import streamlit as st
import pandas as pd
from app.utils import export_to_csv, export_to_excel


def render(df: pd.DataFrame, ch_page):
    # ── Page header ───────────────────────────────────────────────────────
    st.markdown('<div class="page-header">📦 Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-breadcrumb">Home  ▸  Overview</div>', unsafe_allow_html=True)

    # ── KPI Metrics Row ───────────────────────────────────────────────────
    total_products  = df['product_name'].nunique()
    total_volume    = int(df['quantity'].sum())
    last_update     = df['transaction_date'].max().strftime('%d %b %Y')
    total_txns      = len(df)

    # Revenue (if available)
    total_revenue = None
    if 'total_amount' in df.columns:
        total_revenue = df['total_amount'].sum()

    # Period comparison (last 30 vs previous 30 days)
    today = df['transaction_date'].max()
    last_30  = df[df['transaction_date'] >= today - pd.Timedelta(days=30)]
    prev_30  = df[(df['transaction_date'] >= today - pd.Timedelta(days=60)) &
                  (df['transaction_date'] <  today - pd.Timedelta(days=30))]
    vol_delta = None
    if not prev_30.empty:
        pct = ((last_30['quantity'].sum() - prev_30['quantity'].sum()) /
               prev_30['quantity'].sum() * 100)
        vol_delta = f"{pct:+.1f}%"

    if total_revenue is not None:
        c1, c2, c3, c4, c5 = st.columns(5)
    else:
        c1, c2, c3, c4 = st.columns(4)

    c1.metric("🛒 Total Products",   f"{total_products:,}")
    c2.metric("📦 Sales Volume",     f"{total_volume:,}",     delta=vol_delta)
    c3.metric("🧾 Transactions",     f"{total_txns:,}")
    c4.metric("📅 Last Update",      last_update)
    if total_revenue is not None:
        c5.metric("💰 Revenue",      f"₹{total_revenue:,.0f}")

    st.markdown("")

    # ── Quick Actions ─────────────────────────────────────────────────────
    role = st.session_state.user_role

    with st.expander("⚡ Quick Actions", expanded=True):
        if role == 'Admin':
            qa1, qa2, qa3, qa4 = st.columns(4)
            with qa1:
                st.markdown("""<div class="quick-card">
                    <div class="qc-icon">📊</div>
                    <div class="qc-title">Sales Report</div>
                    <div class="qc-desc">View top products & trends</div>
                </div>""", unsafe_allow_html=True)
                if st.button("Open", key="qa_sales", use_container_width=True):
                    ch_page('Sales Analysis'); st.rerun()

            with qa2:
                st.markdown("""<div class="quick-card">
                    <div class="qc-icon">🔮</div>
                    <div class="qc-title">AI Forecast</div>
                    <div class="qc-desc">Predict future demand</div>
                </div>""", unsafe_allow_html=True)
                if st.button("Open", key="qa_forecast", use_container_width=True):
                    ch_page('Inventory Forecast'); st.rerun()

            with qa3:
                st.markdown("""<div class="quick-card">
                    <div class="qc-icon">📦</div>
                    <div class="qc-title">Inventory</div>
                    <div class="qc-desc">Real-time stock tracking</div>
                </div>""", unsafe_allow_html=True)
                if st.button("Open", key="qa_inv", use_container_width=True):
                    ch_page('Inventory Dashboard'); st.rerun()

            with qa4:
                st.markdown("""<div class="quick-card">
                    <div class="qc-icon">📥</div>
                    <div class="qc-title">Stock Inward</div>
                    <div class="qc-desc">Record new arrivals</div>
                </div>""", unsafe_allow_html=True)
                if st.button("Open", key="qa_stock", use_container_width=True):
                    ch_page('Stock Inward'); st.rerun()
        else:
            qa1, qa2, qa3 = st.columns(3)
            with qa1:
                st.markdown("""<div class="quick-card">
                    <div class="qc-icon">➕</div>
                    <div class="qc-title">Add Sale</div>
                    <div class="qc-desc">Record a new transaction</div>
                </div>""", unsafe_allow_html=True)
                if st.button("Open", key="qa_add", use_container_width=True):
                    ch_page('Add Sale'); st.rerun()

            with qa2:
                st.markdown("""<div class="quick-card">
                    <div class="qc-icon">🔮</div>
                    <div class="qc-title">AI Forecast</div>
                    <div class="qc-desc">Predict future demand</div>
                </div>""", unsafe_allow_html=True)
                if st.button("Open", key="qa_forecast", use_container_width=True):
                    ch_page('Inventory Forecast'); st.rerun()

            with qa3:
                st.markdown("""<div class="quick-card">
                    <div class="qc-icon">📦</div>
                    <div class="qc-title">Inventory</div>
                    <div class="qc-desc">Real-time stock tracking</div>
                </div>""", unsafe_allow_html=True)
                if st.button("Open", key="qa_inv", use_container_width=True):
                    ch_page('Inventory Dashboard'); st.rerun()

    st.markdown("")

    # ── Export Data ───────────────────────────────────────────────────────
    with st.expander("📥 Export Sales Data"):
        exp1, exp2, _ = st.columns([1, 1, 2])
        with exp1:
            csv_data, csv_filename = export_to_csv(df, "all_sales_data")
            st.download_button(
                label="📄 Download CSV",
                data=csv_data,
                file_name=csv_filename,
                mime="text/csv",
                use_container_width=True
            )
        with exp2:
            excel_data, excel_filename = export_to_excel(df, "all_sales_data")
            st.download_button(
                label="📊 Download Excel",
                data=excel_data,
                file_name=excel_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    st.markdown("")

    # ── Search & Filter ───────────────────────────────────────────────────
    st.markdown("#### 🔍 Search & Filter")

    filter_col1, filter_col2, filter_col3 = st.columns(3)

    with filter_col1:
        search_query = st.text_input(
            "Search Product",
            placeholder="Type product name...",
            label_visibility="collapsed"
        )

    with filter_col2:
        all_stores = ['All Stores'] + sorted(df['store_name'].dropna().unique().tolist())
        selected_store = st.selectbox("Store", all_stores, label_visibility="collapsed")

    with filter_col3:
        all_sources = ['All Sources'] + sorted(df['data_source'].dropna().unique().tolist())
        selected_source = st.selectbox("Source", all_sources, label_visibility="collapsed")

    filtered_home_df = df.copy()

    if search_query:
        filtered_home_df = filtered_home_df[
            filtered_home_df['product_name'].str.contains(search_query, case=False, na=False)
        ]

    if selected_store != 'All Stores':
        filtered_home_df = filtered_home_df[filtered_home_df['store_name'] == selected_store]

    if selected_source != 'All Sources':
        filtered_home_df = filtered_home_df[filtered_home_df['data_source'] == selected_source]

    active_filters = (search_query or selected_store != 'All Stores' or
                      selected_source != 'All Sources')

    # ── Recent Sales Activity ─────────────────────────────────────────────
    st.markdown("")
    col_hdr, col_count = st.columns([3, 1])
    with col_hdr:
        st.markdown("#### 📋 Recent Sales Activity")
    with col_count:
        if active_filters:
            st.info(f"**{len(filtered_home_df):,}** of {len(df):,} records")

    if not filtered_home_df.empty:
        # Show most recent first
        display_df = filtered_home_df.sort_values('transaction_date', ascending=False).head(15)
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=420
        )
        total = len(filtered_home_df)
        if total > 15:
            st.caption(f"Showing latest 15 of {total:,} records")
    else:
        st.warning("⚠️ No records match your filters")