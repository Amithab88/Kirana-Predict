"""
app/comparison_page.py – Multi-product comparison page.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from app.utils import export_to_csv


def render(df: pd.DataFrame):
    st.title("⚖️ Multi-Product Comparison")
    st.markdown("### Compare sales performance across multiple products")
    st.markdown("---")

    all_products = sorted(df['product_name'].unique().tolist())

    if len(all_products) < 2:
        st.error("❌ Need at least 2 products in database for comparison")
        return

    col_select1, col_select2 = st.columns(2)

    with col_select1:
        num_products = st.slider("How many products to compare?", min_value=2,
                                 max_value=min(4, len(all_products)), value=2)

    with col_select2:
        st.info(f"📦 {len(all_products)} products available in database")

    st.markdown("---")
    st.markdown("**Select Products:**")

    selected_products = []
    cols = st.columns(num_products)

    for i in range(num_products):
        with cols[i]:
            available = [p for p in all_products if p not in selected_products]
            if available:
                product = st.selectbox(f"Product {i+1}", available, key=f"product_select_{i}")
                selected_products.append(product)
            else:
                st.warning("No more products available")

    if len(selected_products) < 2:
        st.warning("⚠️ Please select at least 2 products to compare")
        return

    st.markdown("---")
    date_col1, date_col2 = st.columns(2)

    with date_col1:
        comparison_dates = st.date_input(
            "📅 Comparison Period",
            [df['transaction_date'].min().date(), df['transaction_date'].max().date()],
            key="comparison_dates"
        )

    with date_col2:
        st.info(f"Comparing **{len(selected_products)}** products")

    if len(comparison_dates) != 2:
        st.warning("⚠️ Please select both start and end dates")
        return

    start_date_comp = pd.to_datetime(comparison_dates[0])
    end_date_comp = pd.to_datetime(comparison_dates[1])

    comparison_df = df[
        (df['product_name'].isin(selected_products)) &
        (df['transaction_date'] >= start_date_comp) &
        (df['transaction_date'] <= end_date_comp)
    ]

    if comparison_df.empty:
        st.warning("⚠️ No sales data found for selected products in this period")
        return

    # SUMMARY METRICS
    st.markdown("---")
    st.subheader("📊 Performance Summary")

    metrics_data = []
    for product in selected_products:
        product_df = comparison_df[comparison_df['product_name'] == product]
        metrics_data.append({
            'Product': product,
            'Revenue': f"₹{product_df['total_amount'].sum():,.0f}",
            'Units Sold': f"{product_df['quantity'].sum():,}",
            'Transactions': len(product_df),
            'Avg Price': f"₹{product_df['unit_price'].mean():.2f}"
        })

    metrics_table = pd.DataFrame(metrics_data)
    st.dataframe(metrics_table, use_container_width=True, hide_index=True, height=150)

    # REVENUE COMPARISON
    st.markdown("---")
    st.subheader("💰 Revenue Comparison")

    revenue_comparison = comparison_df.groupby('product_name')['total_amount'].sum().sort_values(ascending=False)
    fig_revenue_comp = px.bar(x=revenue_comparison.index, y=revenue_comparison.values, title='Total Revenue by Product',
                              color=revenue_comparison.values, color_continuous_scale='Blues',
                              labels={'x': 'Product', 'y': 'Revenue (₹)'})
    fig_revenue_comp.update_layout(showlegend=False, height=400)
    st.plotly_chart(fig_revenue_comp, use_container_width=True)

    winner = revenue_comparison.idxmax()
    winner_revenue = revenue_comparison.max()
    st.success(f"🏆 **Top Revenue Generator:** {winner} with ₹{winner_revenue:,.2f}")

    # TRENDS COMPARISON
    st.markdown("---")
    st.subheader("📈 Sales Trends Over Time")

    daily_comparison = comparison_df.groupby(
        [comparison_df['transaction_date'].dt.date, 'product_name']
    )['quantity'].sum().reset_index()
    daily_comparison.columns = ['Date', 'Product', 'Quantity']
    daily_comparison['Date'] = pd.to_datetime(daily_comparison['Date'])

    fig_trends = px.line(daily_comparison, x='Date', y='Quantity', color='Product',
                         title='Daily Sales Trends Comparison', markers=True)
    fig_trends.update_layout(hovermode='x unified', yaxis_title='Units Sold', height=450)
    st.plotly_chart(fig_trends, use_container_width=True)

    # VOLUME COMPARISON
    st.markdown("---")
    st.subheader("📦 Volume Comparison")

    col_units1, col_units2 = st.columns([1.5, 1])

    with col_units1:
        units_comparison = comparison_df.groupby('product_name')['quantity'].sum().sort_values(ascending=False)
        fig_units = px.bar(x=units_comparison.index, y=units_comparison.values, title='Total Units Sold',
                           color=units_comparison.values, color_continuous_scale='Greens',
                           labels={'x': 'Product', 'y': 'Units Sold'})
        fig_units.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig_units, use_container_width=True)

    with col_units2:
        st.markdown("**📊 Volume Rankings**")
        volume_rank = pd.DataFrame({'Rank': range(1, len(units_comparison) + 1),
                                    'Product': units_comparison.index, 'Units': units_comparison.values})
        st.dataframe(volume_rank, use_container_width=True, hide_index=True, height=350)

    # GROWTH ANALYSIS
    st.markdown("---")
    st.subheader("📊 Growth Analysis")

    growth_data = []
    for product in selected_products:
        product_daily = daily_comparison[daily_comparison['Product'] == product].sort_values('Date')
        if len(product_daily) > 1:
            mid_point = len(product_daily) // 2
            first_half = product_daily.head(mid_point)['Quantity'].sum()
            second_half = product_daily.tail(len(product_daily) - mid_point)['Quantity'].sum()
            growth_rate = ((second_half - first_half) / first_half * 100) if first_half > 0 else 0
            growth_data.append({
                'Product': product,
                'First Half Sales': first_half,
                'Second Half Sales': second_half,
                'Growth Rate': f"{growth_rate:+.1f}%",
                'Trend': '📈' if growth_rate > 0 else '📉' if growth_rate < 0 else '➡️'
            })

    if growth_data:
        growth_df = pd.DataFrame(growth_data)
        st.dataframe(growth_df, use_container_width=True, hide_index=True)

        growth_rates = [float(g['Growth Rate'].replace('%', '').replace('+', '')) for g in growth_data]
        if growth_rates:
            best_idx = growth_rates.index(max(growth_rates))
            worst_idx = growth_rates.index(min(growth_rates))
            col_g1, col_g2 = st.columns(2)
            col_g1.success(f"🚀 **Best Growth:** {growth_data[best_idx]['Product']} ({growth_data[best_idx]['Growth Rate']})")
            col_g2.error(f"📉 **Needs Attention:** {growth_data[worst_idx]['Product']} ({growth_data[worst_idx]['Growth Rate']})")

    # PRICE ANALYSIS
    st.markdown("---")
    st.subheader("💵 Price Analysis")

    price_comparison = comparison_df.groupby('product_name')['unit_price'].agg(['mean', 'min', 'max']).round(2)
    price_comparison.columns = ['Average Price', 'Min Price', 'Max Price']
    price_comparison = price_comparison.reset_index()
    price_comparison.columns = ['Product', 'Avg Price (₹)', 'Min Price (₹)', 'Max Price (₹)']
    st.dataframe(price_comparison, use_container_width=True, hide_index=True)

    price_efficiency = []
    for product in selected_products:
        product_df = comparison_df[comparison_df['product_name'] == product]
        total_rev = product_df['total_amount'].sum()
        total_units = product_df['quantity'].sum()
        revenue_per_unit = total_rev / total_units if total_units > 0 else 0
        price_efficiency.append({'Product': product, 'Revenue per Unit': f"₹{revenue_per_unit:.2f}"})

    st.markdown("**💡 Revenue Efficiency:**")
    st.dataframe(pd.DataFrame(price_efficiency), use_container_width=True, hide_index=True)

    # EXPORT
    st.markdown("---")
    st.subheader("📥 Export Comparison Report")

    exp_col1, exp_col2, exp_col3 = st.columns(3)
    comparison_report = comparison_df.copy()
    comparison_report['Date'] = comparison_report['transaction_date'].dt.strftime('%Y-%m-%d')
    comparison_report = comparison_report[['Date', 'product_name', 'quantity', 'unit_price', 'total_amount', 'store_name']]

    with exp_col1:
        comp_csv, comp_csv_name = export_to_csv(comparison_report, f"product_comparison_{len(selected_products)}_products")
        st.download_button("📊 Full Comparison Data (CSV)", data=comp_csv, file_name=comp_csv_name,
                           mime="text/csv", use_container_width=True)

    with exp_col2:
        summary_csv, summary_csv_name = export_to_csv(metrics_table, "comparison_summary")
        st.download_button("📋 Summary Report (CSV)", data=summary_csv, file_name=summary_csv_name,
                           mime="text/csv", use_container_width=True)

    with exp_col3:
        if growth_data:
            growth_csv, growth_csv_name = export_to_csv(pd.DataFrame(growth_data), "growth_analysis")
            st.download_button("📈 Growth Analysis (CSV)", data=growth_csv, file_name=growth_csv_name,
                               mime="text/csv", use_container_width=True)

    # INSIGHTS
    st.markdown("---")
    st.subheader("💡 Key Insights & Recommendations")

    with st.expander("📊 **View AI-Generated Insights**", expanded=True):
        insights = []

        if len(revenue_comparison) >= 2:
            top_product = revenue_comparison.idxmax()
            bottom_product = revenue_comparison.idxmin()
            revenue_gap = ((revenue_comparison.max() - revenue_comparison.min()) / revenue_comparison.min() * 100) if revenue_comparison.min() > 0 else 0
            insights.append(f"💰 **Revenue Gap:** {top_product} generates {revenue_gap:.0f}% more revenue than {bottom_product}")

        if len(units_comparison) >= 2:
            top_volume = units_comparison.idxmax()
            insights.append(f"📦 **Volume Leader:** {top_volume} is the most sold product by units")

        if growth_data and len(growth_data) >= 2:
            growing = [g for g in growth_data if '+' in g['Growth Rate']]
            if growing:
                insights.append(f"📈 **Growth Opportunity:** {len(growing)} product(s) showing positive growth trend")

        price_range = price_comparison['Avg Price (₹)'].max() - price_comparison['Avg Price (₹)'].min()
        if price_range > 0:
            insights.append(f"💵 **Price Range:** Products vary by ₹{price_range:.2f} in average price")

        for insight in insights:
            st.markdown(f"• {insight}")

        st.markdown("---")
        st.markdown("**🎯 Recommendations:**")
        st.markdown("• Focus marketing efforts on high-growth products")
        st.markdown("• Consider bundling high-revenue with high-volume products")
        st.markdown("• Review pricing strategy for low-performing products")
        st.markdown("• Monitor declining trends and investigate causes")
