"""
app/advanced_analytics_page.py – Advanced Analytics Dashboard.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from app.utils import export_to_csv


def render(df: pd.DataFrame):
    st.title("📈 Advanced Analytics Dashboard")
    st.markdown("### Deep Business Insights & Performance Metrics")

    st.markdown("---")
    col_date1, col_date2 = st.columns(2)

    with col_date1:
        analytics_date_range = st.date_input(
            "📅 Analysis Period",
            [df['transaction_date'].min().date(), df['transaction_date'].max().date()],
            key="analytics_date_range"
        )

    with col_date2:
        st.info(f"📊 Analyzing **{len(df)}** total transactions")

    if len(analytics_date_range) != 2:
        return

    start_date_an = pd.to_datetime(analytics_date_range[0])
    end_date_an = pd.to_datetime(analytics_date_range[1])
    df_analytics = df[(df['transaction_date'] >= start_date_an) & (df['transaction_date'] <= end_date_an)].copy()

    if df_analytics.empty:
        st.warning("⚠️ No data in selected period")
        return

    # KEY METRICS
    st.markdown("---")
    st.subheader("📊 Key Performance Indicators")

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

    total_revenue = df_analytics['total_amount'].sum()
    total_transactions = len(df_analytics)
    total_units = df_analytics['quantity'].sum()
    unique_products = df_analytics['product_name'].nunique()
    avg_transaction = total_revenue / total_transactions if total_transactions > 0 else 0

    kpi1.metric("💰 Total Revenue", f"₹{total_revenue:,.0f}")
    kpi2.metric("🧾 Transactions", f"{total_transactions:,}")
    kpi3.metric("📦 Units Sold", f"{total_units:,}")
    kpi4.metric("🛒 Products", f"{unique_products}")
    kpi5.metric("💵 Avg Transaction", f"₹{avg_transaction:.2f}")

    # REVENUE TREND
    st.markdown("---")
    st.subheader("📈 Revenue Trend Analysis")

    trend_col1, trend_col2 = st.columns([2, 1])

    with trend_col1:
        daily_revenue = df_analytics.groupby(df_analytics['transaction_date'].dt.date)['total_amount'].sum().reset_index()
        daily_revenue.columns = ['Date', 'Revenue']

        fig_revenue_trend = px.line(daily_revenue, x='Date', y='Revenue', title='Daily Revenue Trend', markers=True)
        fig_revenue_trend.update_traces(line_color='#2E86AB', line_width=3, marker=dict(size=6))
        fig_revenue_trend.update_layout(hovermode='x unified', yaxis_title='Revenue (₹)', xaxis_title='Date')
        st.plotly_chart(fig_revenue_trend, use_container_width=True)

    with trend_col2:
        st.markdown("**📊 Revenue Statistics**")
        revenue_stats = pd.DataFrame({
            'Metric': ['Average Daily', 'Highest Day', 'Lowest Day', 'Total Days'],
            'Value': [
                f"₹{daily_revenue['Revenue'].mean():,.0f}",
                f"₹{daily_revenue['Revenue'].max():,.0f}",
                f"₹{daily_revenue['Revenue'].min():,.0f}",
                f"{len(daily_revenue)}"
            ]
        })
        st.dataframe(revenue_stats, use_container_width=True, hide_index=True)

        if len(daily_revenue) > 1:
            first_half = daily_revenue.head(len(daily_revenue) // 2)['Revenue'].sum()
            second_half = daily_revenue.tail(len(daily_revenue) // 2)['Revenue'].sum()
            growth = ((second_half - first_half) / first_half * 100) if first_half > 0 else 0
            if growth > 0:
                st.success(f"📈 Growth: +{growth:.1f}%")
            elif growth < 0:
                st.error(f"📉 Decline: {growth:.1f}%")
            else:
                st.info("➡️ Stable")

    # PRODUCT PERFORMANCE
    st.markdown("---")
    st.subheader("🏆 Product Performance Analysis")

    perf_col1, perf_col2 = st.columns(2)
    product_revenue = df_analytics.groupby('product_name')['total_amount'].sum().sort_values(ascending=False)

    with perf_col1:
        top_5 = product_revenue.head(5)
        fig_top5 = px.bar(x=top_5.values, y=top_5.index, orientation='h', title='Top 5 Products by Revenue',
                          color=top_5.values, color_continuous_scale='Greens')
        fig_top5.update_layout(xaxis_title='Revenue (₹)', yaxis_title='', showlegend=False, height=300)
        st.plotly_chart(fig_top5, use_container_width=True)

    with perf_col2:
        bottom_5 = product_revenue.tail(5).sort_values()
        fig_bottom5 = px.bar(x=bottom_5.values, y=bottom_5.index, orientation='h', title='Bottom 5 Products by Revenue',
                             color=bottom_5.values, color_continuous_scale='Reds')
        fig_bottom5.update_layout(xaxis_title='Revenue (₹)', yaxis_title='', showlegend=False, height=300)
        st.plotly_chart(fig_bottom5, use_container_width=True)

    # SALES DISTRIBUTION
    st.markdown("---")
    st.subheader("🥧 Sales Distribution Analysis")

    dist_col1, dist_col2 = st.columns([1.5, 1])

    with dist_col1:
        product_quantity = df_analytics.groupby('product_name')['quantity'].sum().head(8)
        fig_pie = px.pie(values=product_quantity.values, names=product_quantity.index,
                         title='Product Sales Distribution (Top 8)', hole=0.4)
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

    with dist_col2:
        st.markdown("**📊 Distribution Summary**")
        dist_summary = pd.DataFrame({
            'Product': product_quantity.index[:5],
            'Units': product_quantity.values[:5],
            '% of Total': [f"{(v / product_quantity.sum() * 100):.1f}%" for v in product_quantity.values[:5]]
        })
        st.dataframe(dist_summary, use_container_width=True, hide_index=True, height=250)

    # TIME-BASED PATTERNS
    st.markdown("---")
    st.subheader("📅 Time-Based Sales Patterns")

    time_col1, time_col2 = st.columns(2)

    with time_col1:
        df_analytics['day_of_week'] = df_analytics['transaction_date'].dt.day_name()
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        dow_sales = df_analytics.groupby('day_of_week')['total_amount'].sum().reindex(day_order).fillna(0)
        fig_dow = px.bar(x=dow_sales.index, y=dow_sales.values, title='Sales by Day of Week',
                         color=dow_sales.values, color_continuous_scale='Blues', labels={'x': 'Day', 'y': 'Revenue (₹)'})
        fig_dow.update_layout(showlegend=False)
        st.plotly_chart(fig_dow, use_container_width=True)

    with time_col2:
        df_analytics['month'] = df_analytics['transaction_date'].dt.to_period('M').astype(str)
        monthly_sales = df_analytics.groupby('month')['total_amount'].sum()
        if len(monthly_sales) > 1:
            fig_monthly = px.line(x=monthly_sales.index, y=monthly_sales.values,
                                  title='Monthly Revenue Trend', markers=True)
            fig_monthly.update_traces(line_color='#F77F00', line_width=3, marker=dict(size=8))
            fig_monthly.update_layout(xaxis_title='Month', yaxis_title='Revenue (₹)')
            st.plotly_chart(fig_monthly, use_container_width=True)
        else:
            st.info("📊 Need data from multiple months for monthly trend analysis")

    # STORE PERFORMANCE (multi-store only)
    if df_analytics['store_name'].nunique() > 1:
        st.markdown("---")
        st.subheader("🏪 Store Performance Comparison")

        store_revenue = df_analytics.groupby('store_name').agg({
            'total_amount': 'sum', 'quantity': 'sum', 'transaction_id': 'count'
        }).round(2)
        store_revenue.columns = ['Revenue', 'Units Sold', 'Transactions']
        store_revenue = store_revenue.sort_values('Revenue', ascending=False)

        store_col1, store_col2 = st.columns([1.5, 1])

        with store_col1:
            fig_store = px.bar(store_revenue, x=store_revenue.index, y='Revenue',
                               title='Revenue by Store', color='Revenue', color_continuous_scale='Teal')
            fig_store.update_layout(showlegend=False, xaxis_title='Store', yaxis_title='Revenue (₹)')
            st.plotly_chart(fig_store, use_container_width=True)

        with store_col2:
            st.markdown("**🏆 Store Rankings**")
            store_revenue_display = store_revenue.copy()
            store_revenue_display['Revenue'] = store_revenue_display['Revenue'].apply(lambda x: f"₹{x:,.0f}")
            st.dataframe(store_revenue_display, use_container_width=True, height=300)

    # EXPORT
    st.markdown("---")
    st.subheader("📥 Export Analytics Report")

    export_col1, export_col2, export_col3 = st.columns(3)

    analytics_report = pd.DataFrame({
        'Metric': ['Total Revenue', 'Total Transactions', 'Total Units Sold', 'Unique Products',
                   'Average Transaction Value', 'Best Selling Product', 'Highest Revenue Product', 'Analysis Period'],
        'Value': [
            f"₹{total_revenue:,.2f}", total_transactions, total_units, unique_products,
            f"₹{avg_transaction:.2f}",
            df_analytics.groupby('product_name')['quantity'].sum().idxmax(),
            product_revenue.idxmax(),
            f"{start_date_an.strftime('%d %b %Y')} - {end_date_an.strftime('%d %b %Y')}"
        ]
    })

    with export_col1:
        report_csv, report_csv_name = export_to_csv(analytics_report, "analytics_summary")
        st.download_button("📊 Summary Report (CSV)", data=report_csv, file_name=report_csv_name,
                           mime="text/csv", use_container_width=True)

    with export_col2:
        product_perf_csv, product_perf_name = export_to_csv(
            df_analytics.groupby('product_name').agg({
                'quantity': 'sum', 'total_amount': 'sum', 'transaction_id': 'count'
            }).reset_index(), "product_performance"
        )
        st.download_button("🛒 Product Performance (CSV)", data=product_perf_csv, file_name=product_perf_name,
                           mime="text/csv", use_container_width=True)

    with export_col3:
        daily_report_csv, daily_report_name = export_to_csv(daily_revenue, "daily_revenue")
        st.download_button("📅 Daily Revenue (CSV)", data=daily_report_csv, file_name=daily_report_name,
                           mime="text/csv", use_container_width=True)
