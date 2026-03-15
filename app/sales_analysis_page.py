"""
app/sales_analysis_page.py – Sales Analysis page with filters, charts, and exports.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from app.utils import export_to_csv


def render(df: pd.DataFrame):
    st.title("📊 Sales Insights")

    # Filter section
    st.subheader("🔍 Filter Data")

    filter_row1_col1, filter_row1_col2 = st.columns(2)

    with filter_row1_col1:
        date_range = st.date_input(
            "📅 Select Date Range:",
            [df['transaction_date'].min().date(),
             df['transaction_date'].max().date()]
        )

    with filter_row1_col2:
        all_products = df['product_name'].unique().tolist()
        selected_products = st.multiselect(
            "🛒 Select Products (leave empty for all)",
            all_products,
            help="Select specific products or leave empty to show all"
        )

    filter_row2_col1, filter_row2_col2 = st.columns(2)

    with filter_row2_col1:
        all_stores_analysis = ['All Stores'] + sorted(df['store_name'].dropna().unique().tolist())
        selected_store_analysis = st.selectbox(
            "🏪 Store",
            all_stores_analysis,
            key="store_filter_analysis"
        )

    with filter_row2_col2:
        sort_options = {
            'Date (Newest First)': ('transaction_date', False),
            'Date (Oldest First)': ('transaction_date', True),
            'Quantity (Highest First)': ('quantity', False),
            'Quantity (Lowest First)': ('quantity', True),
            'Amount (Highest First)': ('total_amount', False),
            'Amount (Lowest First)': ('total_amount', True),
        }
        selected_sort = st.selectbox("📊 Sort By", list(sort_options.keys()))

    st.markdown("---")

    if len(date_range) == 2:
        if date_range[0] > date_range[1]:
            st.error("❌ Start date must be before end date")
            st.stop()

        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        filtered_df = df[(df['transaction_date'] >= start_date) & (df['transaction_date'] <= end_date)]

        if selected_products:
            filtered_df = filtered_df[filtered_df['product_name'].isin(selected_products)]

        if selected_store_analysis != 'All Stores':
            filtered_df = filtered_df[filtered_df['store_name'] == selected_store_analysis]

        sort_column, sort_ascending = sort_options[selected_sort]
        if sort_column in filtered_df.columns:
            filtered_df = filtered_df.sort_values(by=sort_column, ascending=sort_ascending)

        if filtered_df.empty:
            st.warning("⚠️ No sales data matches your filters")
            st.stop()

        st.success(
            f"✅ Found **{len(filtered_df)}** transactions | "
            f"**{filtered_df['product_name'].nunique()}** unique products | "
            f"Total: **₹{filtered_df['total_amount'].sum():,.2f}**"
        )

        top_items = filtered_df.groupby('product_name')['quantity'].sum().sort_values(ascending=False).head(10)

        if not top_items.empty:
            col_chart, col_data = st.columns([2, 1])

            with col_chart:
                fig = px.bar(
                    top_items,
                    x=top_items.index,
                    y=top_items.values,
                    title="Top 10 Best Sellers",
                    color=top_items.values,
                    color_continuous_scale='Viridis',
                    labels={'y': 'Units Sold', 'x': 'Product'}
                )
                fig.update_layout(showlegend=False, xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)

            with col_data:
                st.markdown("**📊 Top 10 Products**")
                top_items_df = pd.DataFrame({
                    'Product': top_items.index,
                    'Quantity': top_items.values
                })
                st.dataframe(top_items_df, use_container_width=True, height=400)

            # Export options
            st.markdown("---")
            st.subheader("📥 Export Data")

            col_exp1, col_exp2 = st.columns(2)

            with col_exp1:
                csv_data, csv_filename = export_to_csv(
                    filtered_df,
                    f"sales_analysis_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
                )
                st.download_button(
                    label="📥 Download Filtered Sales (CSV)",
                    data=csv_data,
                    file_name=csv_filename,
                    mime="text/csv",
                    use_container_width=True
                )

            with col_exp2:
                summary_df = pd.DataFrame({
                    'Product': top_items.index,
                    'Total Sales': top_items.values
                })
                csv_summary, csv_summary_filename = export_to_csv(
                    summary_df,
                    f"top_products_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
                )
                st.download_button(
                    label="📊 Download Top Products Report (CSV)",
                    data=csv_summary,
                    file_name=csv_summary_filename,
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.warning("No data found for this period.")
