"""
app/forecasting_page.py – AI-Powered Inventory Forecast using Prophet ML.
Accessible to all logged-in users (Admin and Staff).
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from app.utils import export_to_csv, export_to_excel
from core.ml_engine import predict_future_demand


def render(df: pd.DataFrame):
    st.title("🔮 Smart Inventory Forecaster")

    # ── Product selection ──────────────────────────────────────────────────
    st.subheader("🔍 Select Product")

    search_col, select_col = st.columns([1, 2])

    with search_col:
        product_search = st.text_input(
            "🔎 Search Product",
            placeholder="Type to filter...",
            key="product_search_forecast"
        )

    all_products_forecast = sorted(df['product_name'].unique().tolist())

    if product_search:
        filtered_products = [p for p in all_products_forecast if product_search.lower() in p.lower()]
        if not filtered_products:
            st.warning(f"⚠️ No products match '{product_search}'")
            return
    else:
        filtered_products = all_products_forecast

    with select_col:
        st.caption(f"📦 {len(filtered_products)} product(s) available")
        item = st.selectbox(
            "Choose Product:",
            filtered_products,
            key="product_select_forecast"
        )

    # ── Filter data for selected product ───────────────────────────────────
    item_data = df[df['product_name'] == item].copy()

    if item_data.empty:
        st.error(f"❌ No sales data found for '{item}'")
        return

    # ── User inputs ────────────────────────────────────────────────────────
    col_input1, col_input2 = st.columns(2)

    with col_input1:
        stock = st.number_input("Current Physical Stock:", min_value=0, value=50)

    with col_input2:
        days_to_consider = st.slider("Lookback Period (Days):", 7, 90, 30)

    # ── Calculate metrics ──────────────────────────────────────────────────
    max_date = item_data['transaction_date'].max()
    cutoff = max_date - pd.Timedelta(days=days_to_consider)
    recent_data = item_data[item_data['transaction_date'] >= cutoff]

    if recent_data.empty:
        st.warning(f"⚠️ No sales data for {item} in the last {days_to_consider} days.")
        st.info("💡 Try increasing the lookback period or select a different product.")
        return

    avg_sales = recent_data['quantity'].sum() / recent_data['transaction_date'].nunique()
    days_left = stock / avg_sales if avg_sales > 0 else 0

    # ── Key metrics ────────────────────────────────────────────────────────
    m1, m2, m3 = st.columns(3)
    m1.metric("📦 Current Stock", stock)
    m2.metric("📈 Avg Daily Sales", f"{round(avg_sales, 1)} units")
    m3.metric("⏰ Days Left", f"{round(days_left, 1)} days")

    if days_left < 3:
        st.error(f"🚨 CRITICAL: Only {round(days_left, 1)} days of stock remaining!")
    elif days_left < 7:
        st.warning(f"⚠️ Low Stock: Restock within a week ({round(days_left, 1)} days left)")
    else:
        st.success(f"✅ Stock levels healthy ({round(days_left, 1)} days remaining)")

    # ── Historical sales trend ─────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📊 Historical Sales Trend")

    daily_sales = recent_data.groupby('transaction_date')['quantity'].sum().reset_index()

    if not daily_sales.empty:
        fig_trend = px.line(
            daily_sales,
            x='transaction_date',
            y='quantity',
            title=f"{item} – Sales Trend (Last {days_to_consider} Days)",
            labels={'quantity': 'Units Sold', 'transaction_date': 'Date'}
        )
        fig_trend.update_traces(line_color='#1f77b4', line_width=2)
        fig_trend.update_layout(hovermode='x unified')
        st.plotly_chart(fig_trend, use_container_width=True)

    # ── AI Forecast section ────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🚀 AI-Powered 7-Day Forecast")

    unique_days = item_data['transaction_date'].nunique()
    total_records = len(item_data)

    col_info1, col_info2 = st.columns(2)
    col_info1.info(f"📅 Available Data: **{unique_days} unique days**")
    col_info2.info(f"📊 Total Transactions: **{total_records} records**")

    if st.button("🔮 Generate Future Forecast", type="primary"):
        if unique_days < 7:
            st.error("❌ Insufficient Data: Need at least 7 days of sales history.")
            st.warning(f"Currently have: **{unique_days} days**")
            st.info(
                "💡 **Solutions:**\n"
                "- Add more historical data in Supabase\n"
                "- Select a different product with more history"
            )
        else:
            with st.spinner("🤖 AI is analyzing sales patterns..."):
                try:
                    forecast, metrics_dict = predict_future_demand(item_data)
                    accuracy = metrics_dict.get('accuracy', 0) / 100 if metrics_dict else 0

                    if forecast is None:
                        st.error("❌ Prediction failed. Please try a different product or date range.")
                    else:
                        col1, col2 = st.columns([1, 2])

                        with col1:
                            st.markdown("**📅 Next Week's Prediction:**")
                            display_forecast = forecast[['Date', 'Predicted_Sales']].copy()
                            display_forecast['Date'] = pd.to_datetime(display_forecast['Date']).dt.strftime('%d %b %Y')
                            st.dataframe(display_forecast.set_index('Date'), use_container_width=True, height=280)

                            if accuracy > 0.7:
                                st.success(f"**Model Accuracy:** {round(accuracy * 100, 1)}%")
                            elif accuracy > 0.4:
                                st.warning(f"**Model Accuracy:** {round(accuracy * 100, 1)}%")
                            else:
                                st.error(f"**Model Accuracy:** {round(accuracy * 100, 1)}%")
                            st.caption("⚠️ Low accuracy indicates unpredictable sales patterns")

                        with col2:
                            st.markdown("**📈 Forecast Visualization:**")
                            fig_forecast = px.line(
                                forecast,
                                x='Date',
                                y='Predicted_Sales',
                                title=f"AI Forecast: {item}",
                                markers=True
                            )
                            fig_forecast.update_traces(
                                line_color='orange', line_width=3, marker=dict(size=8)
                            )
                            fig_forecast.update_layout(
                                xaxis_title="Date",
                                yaxis_title="Predicted Sales (Units)",
                                hovermode='x unified'
                            )
                            st.plotly_chart(fig_forecast, use_container_width=True)

                        # ── Export forecast ────────────────────────────────
                        st.markdown("---")
                        st.subheader("📥 Export Forecast")

                        col_e1, col_e2 = st.columns(2)

                        with col_e1:
                            forecast_csv, forecast_csv_filename = export_to_csv(
                                forecast[['Date', 'Predicted_Sales']],
                                f"forecast_{item.replace(' ', '_')}"
                            )
                            st.download_button(
                                label=f"📥 Download {item} Forecast (CSV)",
                                data=forecast_csv,
                                file_name=forecast_csv_filename,
                                mime="text/csv",
                                use_container_width=True
                            )

                        with col_e2:
                            detailed_forecast = forecast.copy()
                            detailed_forecast['Product'] = item
                            detailed_forecast['Stock_On_Hand'] = stock
                            detailed_forecast['Forecast_Generated'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                            forecast_excel, forecast_excel_filename = export_to_excel(
                                detailed_forecast,
                                f"detailed_forecast_{item.replace(' ', '_')}"
                            )
                            st.download_button(
                                label="📊 Download Detailed Report (Excel)",
                                data=forecast_excel,
                                file_name=forecast_excel_filename,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )

                        # ── Business insights ──────────────────────────────
                        total_needed = forecast['Predicted_Sales'].sum()
                        avg_daily_forecast = forecast['Predicted_Sales'].mean()
                        forecast_days_left = stock / avg_daily_forecast if avg_daily_forecast > 0 else 0

                        st.markdown("---")
                        st.markdown("### 💡 Business Insights")

                        insight_col1, insight_col2, insight_col3 = st.columns(3)
                        insight_col1.metric("📦 Total Needed (7 days)", f"{round(total_needed)} units")
                        insight_col2.metric("📊 Avg Daily Forecast", f"{round(avg_daily_forecast, 1)} units/day")
                        insight_col3.metric("⏰ Forecast Days Left", f"{round(forecast_days_left, 1)} days")

                        if forecast_days_left < 7:
                            st.error("🚨 **Action Required:** Stock will run out before end of forecast period!")
                            st.info(f"💡 **Recommendation:** Order at least {round(total_needed - stock)} more units")
                        elif forecast_days_left < 14:
                            st.warning("⚠️ **Caution:** Stock adequate for forecast period, but monitor closely")
                            st.info(f"💡 **Recommendation:** Consider ordering {round(total_needed * 0.5)} units for buffer")
                        else:
                            st.success("✅ **All Good:** Current stock sufficient for forecast period")

                except Exception as e:
                    st.error(f"❌ Prediction Error: {str(e)}")
                    st.info("💡 Try selecting a different product or adjusting the lookback period")
                    with st.expander("🔍 Debug Information"):
                        st.code(str(e))
                        st.write("**Item Data Shape:**", item_data.shape)
                        st.write(
                            "**Date Range:**",
                            item_data['transaction_date'].min(), "to",
                            item_data['transaction_date'].max()
                        )
