import streamlit as st
import pandas as pd
import plotly.express as px
from database_manager import load_data_from_db
from ml_engine import predict_future_demand
from datetime import datetime
import io

# ============================================
# EXPORT HELPER FUNCTIONS
# ============================================

def export_to_csv(dataframe, filename_prefix):
    """Convert DataFrame to CSV for download"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv = dataframe.to_csv(index=False)
    return csv, f"{filename_prefix}_{timestamp}.csv"

def export_to_excel(dataframe, filename_prefix):
    """Convert DataFrame to Excel for download"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        dataframe.to_excel(writer, index=False, sheet_name='Data')
    output.seek(0)
    return output.getvalue(), f"{filename_prefix}_{timestamp}.xlsx"

# Page Config
st.set_page_config(page_title="Kirana-Predict Pro", layout="wide", page_icon="📦")

# Data Loading
try:
    df = load_data_from_db()
    if df.empty:
        st.error("❌ No data in database. Please add sales data in Supabase.")
        st.stop()
except Exception as e:
    st.error(f"❌ Database connection failed: {str(e)}")
    st.info("💡 Check your .env file and Supabase credentials")
    st.stop()

try:
    # Prefer an explicit transaction date column if present
    if 'transaction_date' in df.columns:
        df['transaction_date'] = pd.to_datetime(df['transaction_date'])
    # Fallback: some pipelines may only store created_at
    elif 'created_at' in df.columns:
        df['transaction_date'] = pd.to_datetime(df['created_at'])
    else:
        raise KeyError(
            f"No date column found. Expected 'transaction_date' or 'created_at'. "
            f"Available columns: {list(df.columns)}"
        )
except Exception as e:
    st.error(f"❌ Date conversion error: {str(e)}")
    st.stop()

# Normalize optional columns used in filters/metrics
if 'store_name' not in df.columns:
    df['store_name'] = 'Main Store'

if 'data_source' not in df.columns:
    df['data_source'] = 'manual'

if 'total_amount' not in df.columns and 'quantity' in df.columns and 'unit_price' in df.columns:
    df['total_amount'] = df['quantity'] * df['unit_price']

# 1. Initialize session state for navigation
if 'page' not in st.session_state:
    st.session_state.page = 'Home'

# 2. Function to change pages
def ch_page(page_name):
    st.session_state.page = page_name

# 3. Top Navigation Bar
if st.session_state.page != 'Home':
    if st.button("⬅️ Back to Home"):
        ch_page('Home')
        st.rerun()

# ============================================
# HUB PAGE (Card Layout)
# ============================================
if st.session_state.page == 'Home':
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
        if 'store_name' in df.columns:
            all_stores = ['All Stores'] + sorted(df['store_name'].dropna().unique().tolist())
        else:
            all_stores = ['All Stores']
        selected_store = st.selectbox("🏪 Filter by Store", all_stores)
    
    with filter_col3:
        if 'data_source' in df.columns:
            all_sources = ['All Sources'] + sorted(df['data_source'].dropna().unique().tolist())
        else:
            all_sources = ['All Sources']
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
    
    with col1:
        st.subheader("📊 Sales Analytics")
        st.info("📈 View top-selling products and historical sales trends.")
        if st.button("Open Sales Analysis", use_container_width=True, type="primary"):
            ch_page('Sales Analysis')
            st.rerun()
    
    with col2:
        st.subheader("🔮 AI Forecasting")
        st.success("🤖 Predict future demand and get restock alerts using Machine Learning.")
        if st.button("Open Inventory Forecast", use_container_width=True, type="primary"):
            ch_page('Inventory Forecast')
            st.rerun()
    
    # Recent Activity Preview (filtered)
    st.markdown("---")
    st.subheader("📋 Recent Sales Activity")
    
    if not filtered_home_df.empty:
        display_df = filtered_home_df.head(10)
        st.dataframe(display_df, use_container_width=True)
        if len(filtered_home_df) > 10:
            st.caption(f"Showing 10 of {len(filtered_home_df)} records")
    else:
        st.warning("⚠️ No records match your filters")

# ============================================
# SALES ANALYSIS PAGE
# ============================================
elif st.session_state.page == 'Sales Analysis':
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
            
            # Export options for filtered data and summary (from Feature 1)
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

# ============================================
# INVENTORY FORECAST PAGE
# ============================================
elif st.session_state.page == 'Inventory Forecast':
    st.title("🔮 Smart Inventory Forecaster")
    
    # Product search and selection
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
            st.stop()
    else:
        filtered_products = all_products_forecast
    
    with select_col:
        st.caption(f"📦 {len(filtered_products)} product(s) available")
        item = st.selectbox(
            "Choose Product:",
            filtered_products,
            key="product_select_forecast"
        )
    
    # ✅ STEP 2: Filter data for selected product IMMEDIATELY
    item_data = df[df['product_name'] == item].copy()
    
    # ✅ STEP 3: Check if product has any data
    if item_data.empty:
        st.error(f"❌ No sales data found for '{item}'")
        st.stop()  # Stop execution here
    
    # ✅ STEP 4: User inputs (now safe because item_data exists)
    col_input1, col_input2 = st.columns(2)
    
    with col_input1:
        stock = st.number_input("Current Physical Stock:", min_value=0, value=50)
    
    with col_input2:
        days_to_consider = st.slider("Lookback Period (Days):", 7, 90, 30)
    
    # ✅ STEP 5: Calculate metrics (using already defined item_data)
    max_date = item_data['transaction_date'].max()
    cutoff = max_date - pd.Timedelta(days=days_to_consider)
    recent_data = item_data[item_data['transaction_date'] >= cutoff]
    
    # ✅ STEP 6: Check if we have recent data
    if recent_data.empty:
        st.warning(f"⚠️ No sales data for {item} in the last {days_to_consider} days.")
        st.info("💡 Try increasing the lookback period or select a different product.")
        st.stop()  # Stop execution here
    
    # ✅ STEP 7: Calculate daily metrics
    avg_sales = recent_data['quantity'].sum() / recent_data['transaction_date'].nunique()
    days_left = stock / avg_sales if avg_sales > 0 else 0
    
    # ✅ STEP 8: Display metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("📦 Current Stock", stock)
    m2.metric("📈 Avg Daily Sales", f"{round(avg_sales, 1)} units")
    m3.metric("⏰ Days Left", f"{round(days_left, 1)} days")
    
    # ✅ STEP 9: Stock alerts
    if days_left < 3:
        st.error(f"🚨 CRITICAL: Only {round(days_left, 1)} days of stock remaining!")
    elif days_left < 7:
        st.warning(f"⚠️ Low Stock: Restock within a week ({round(days_left, 1)} days left)")
    else:
        st.success(f"✅ Stock levels healthy ({round(days_left, 1)} days remaining)")
    
    # ✅ STEP 10: Sales trend chart
    st.markdown("---")
    st.subheader("📊 Historical Sales Trend")
    
    daily_sales = recent_data.groupby('transaction_date')['quantity'].sum().reset_index()
    
    if not daily_sales.empty:
        fig_trend = px.line(
            daily_sales,
            x='transaction_date',
            y='quantity',
            title=f"{item} - Sales Trend (Last {days_to_consider} Days)",
            labels={'quantity': 'Units Sold', 'transaction_date': 'Date'}
        )
        fig_trend.update_traces(line_color='#1f77b4', line_width=2)
        fig_trend.update_layout(hovermode='x unified')
        st.plotly_chart(fig_trend, use_container_width=True)
    
    # ✅ STEP 11: AI Prediction Section
    st.markdown("---")
    st.subheader("🚀 AI-Powered 7-Day Forecast")
    
    # Show data availability info
    unique_days = item_data['transaction_date'].nunique()
    total_records = len(item_data)
    
    col_info1, col_info2 = st.columns(2)
    col_info1.info(f"📅 Available Data: **{unique_days} unique days**")
    col_info2.info(f"📊 Total Transactions: **{total_records} records**")
    
    # ✅ STEP 12: AI Prediction Button (with proper validation)
    if st.button("🔮 Generate Future Forecast", type="primary"):
        # Validate data availability
        if unique_days < 7:
            st.error(f"❌ Insufficient Data: Need at least 7 days of sales history.")
            st.warning(f"Currently have: **{unique_days} days**")
            st.info("💡 **Solutions:**\n- Add more historical data in Supabase\n- Select a different product with more history")
        else:
            # Show loading spinner
            with st.spinner('🤖 AI is analyzing sales patterns...'):
                try:
                    # Call prediction function
                    forecast, metrics_dict = predict_future_demand(item_data)
                    # Extract the accuracy number from the dictionary, or default to 0
                    accuracy = metrics_dict.get('accuracy', 0) / 100 if metrics_dict else 0
                    
                    if forecast is None:
                        st.error("❌ Prediction failed. Please try a different product or date range.")
                    else:
                        # Display results
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            st.markdown("**📅 Next Week's Prediction:**")
                            
                            # Format the forecast table
                            display_forecast = forecast[['Date', 'Predicted_Sales']].copy()
                            display_forecast['Date'] = pd.to_datetime(display_forecast['Date']).dt.strftime('%d %b %Y')
                            
                            st.dataframe(
                                display_forecast.set_index('Date'),
                                use_container_width=True,
                                height=280
                            )
                            
                            # Show accuracy with color coding
                            if accuracy > 0.7:
                                st.success(f"**Model Accuracy:** {round(accuracy * 100, 1)}%")
                            elif accuracy > 0.4:
                                st.warning(f"**Model Accuracy:** {round(accuracy * 100, 1)}%")
                            else:
                                st.error(f"**Model Accuracy:** {round(accuracy * 100, 1)}%")
                            
                            st.caption("⚠️ Low accuracy indicates unpredictable sales patterns")
                        
                        with col2:
                            st.markdown("**📈 Forecast Visualization:**")
                            
                            # Create forecast chart
                            fig_forecast = px.line(
                                forecast,
                                x='Date',
                                y='Predicted_Sales',
                                title=f"AI Forecast: {item}",
                                markers=True
                            )
                            fig_forecast.update_traces(
                                line_color='orange',
                                line_width=3,
                                marker=dict(size=8)
                            )
                            fig_forecast.update_layout(
                                xaxis_title="Date",
                                yaxis_title="Predicted Sales (Units)",
                                hovermode='x unified'
                            )
                            st.plotly_chart(fig_forecast, use_container_width=True)
                        
                        # Export forecast data
                        st.markdown("---")
                        st.subheader("📥 Export Forecast")
                        
                        col_forecast_export1, col_forecast_export2 = st.columns(2)
                        
                        with col_forecast_export1:
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
                        
                        with col_forecast_export2:
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
                        
                        # Calculate total needed
                        total_needed = forecast['Predicted_Sales'].sum()
                        avg_daily_forecast = forecast['Predicted_Sales'].mean()
                        
                        # Business insights
                        st.markdown("---")
                        st.markdown("### 💡 Business Insights")
                        
                        insight_col1, insight_col2, insight_col3 = st.columns(3)
                        
                        insight_col1.metric(
                            "📦 Total Needed (7 days)",
                            f"{round(total_needed)} units"
                        )
                        
                        insight_col2.metric(
                            "📊 Avg Daily Forecast",
                            f"{round(avg_daily_forecast, 1)} units/day"
                        )
                        
                        # Compare forecast vs current burn rate
                        forecast_days_left = stock / avg_daily_forecast if avg_daily_forecast > 0 else 0
                        insight_col3.metric(
                            "⏰ Forecast Days Left",
                            f"{round(forecast_days_left, 1)} days"
                        )
                        
                        # Recommendation
                        if forecast_days_left < 7:
                            st.error(f"🚨 **Action Required:** Stock will run out before end of forecast period!")
                            st.info(f"💡 **Recommendation:** Order at least {round(total_needed - stock)} more units")
                        elif forecast_days_left < 14:
                            st.warning(f"⚠️ **Caution:** Stock adequate for forecast period, but monitor closely")
                            st.info(f"💡 **Recommendation:** Consider ordering {round(total_needed * 0.5)} units for buffer")
                        else:
                            st.success(f"✅ **All Good:** Current stock sufficient for forecast period")
                
                except Exception as e:
                    st.error(f"❌ Prediction Error: {str(e)}")
                    st.info("💡 Try selecting a different product or adjusting the lookback period")
                    
                    # Show debug info in expander
                    with st.expander("🔍 Debug Information"):
                        st.write("**Error Details:**")
                        st.code(str(e))
                        st.write("**Item Data Shape:**", item_data.shape)
                        st.write("**Date Range:**", item_data['transaction_date'].min(), "to", item_data['transaction_date'].max())