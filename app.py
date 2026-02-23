import streamlit as st
import pandas as pd
import plotly.express as px
from database_manager import load_data_from_db
from ml_engine import predict_future_demand

# Page Config
st.set_page_config(page_title="Kirana-Predict Pro", layout="wide", page_icon="📦")

# Data Loading
df = load_data_from_db()
df['transaction_date'] = pd.to_datetime(df['transaction_date'])

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
    
    # Optional: Recent Activity Preview
    st.markdown("---")
    st.subheader("📋 Recent Sales Activity")
    st.dataframe(df.head(5), use_container_width=True)

# ============================================
# SALES ANALYSIS PAGE
# ============================================
elif st.session_state.page == 'Sales Analysis':
    st.title("📊 Sales Insights")
    
    date_range = st.date_input("📅 Select Date Range:", 
                                [df['transaction_date'].min().date(), 
                                 df['transaction_date'].max().date()])
    
    if len(date_range) == 2:
        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        filtered_df = df[(df['transaction_date'] >= start_date) & (df['transaction_date'] <= end_date)]
        
        top_items = filtered_df.groupby('product_name')['quantity'].sum().sort_values(ascending=False).head(5)
        
        if not top_items.empty:
            fig = px.bar(top_items, x=top_items.index, y=top_items.values,
                         title="Top 5 Best Sellers", color=top_items.values,
                         color_continuous_scale='Viridis', labels={'y':'Units Sold', 'x':''})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No data found for this period.")

# ============================================
# INVENTORY FORECAST PAGE
# ============================================
elif st.session_state.page == 'Inventory Forecast':
    st.title("🔮 Smart Inventory Forecaster")
    
    item = st.selectbox("Select Product:", df['product_name'].unique())
    stock = st.number_input("Current Physical Stock:", min_value=0, value=50)
    days_to_consider = st.slider("Lookback Period (Days):", 7, 90, 30)
    
    item_data = df[df['product_name'] == item]
    
    if not item_data.empty:
        max_date = item_data['transaction_date'].max()
        cutoff = max_date - pd.Timedelta(days=days_to_consider)
        recent_data = item_data[item_data['transaction_date'] >= cutoff]
        
        if not recent_data.empty:
            avg_sales = recent_data['quantity'].sum() / recent_data['transaction_date'].nunique()
            days_left = stock / avg_sales if avg_sales > 0 else 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Current Stock", stock)
            m2.metric("Avg Daily Sales", f"{round(avg_sales, 1)}")
            m3.metric("Est. Days Left", f"{round(days_left, 1)}")
            
            if days_left < 3: 
                st.error(f"🚨 ORDER NOW: Running out in {round(days_left, 1)} days!")
            elif days_left < 7: 
                st.warning(f"⚠️ Low Stock: Restock within a week.")
            else: 
                st.success("✅ Stock levels healthy.")
            
            st.subheader("📈 Sales Trend")
            daily_sales = recent_data.groupby('transaction_date')['quantity'].sum().reset_index()
            fig = px.line(daily_sales, x='transaction_date', y='quantity',
                         title=f"{item} - Last {days_to_consider} Days",
                         labels={'quantity': 'Units Sold', 'transaction_date': 'Date'})
            st.plotly_chart(fig, use_container_width=True)
            
            # AI PREDICTION SECTION
            st.markdown("---")
            st.subheader("🚀 AI-Powered 7-Day Forecast")

            if st.button("🔮 Generate Future Forecast", type="primary"):
                if len(item_data) < 7:
                    st.warning("⚠️ Need at least 7 days of sales history.")
                else:
                    forecast, accuracy = predict_future_demand(item_data)
                    
                    if forecast is None:
                        st.error("❌ Insufficient data for prediction.")
                    else:
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            st.write("**📅 Next Week's Prediction:**")
                            st.dataframe(forecast.set_index('Date'), use_container_width=True)
                            
                            confidence_color = "green" if accuracy > 0.7 else "orange" if accuracy > 0.4 else "red"
                            st.markdown(f"**Model Accuracy:** :{confidence_color}[{round(accuracy * 100, 1)}%]")
                        
                        with col2:
                            fig_forecast = px.line(forecast, x='Date', y='Predicted_Sales', 
                                                   title=f"AI Forecast: {item}",
                                                   markers=True)
                            fig_forecast.update_traces(line_color='orange', line_width=3)
                            st.plotly_chart(fig_forecast, use_container_width=True)
                            
                        total_needed = forecast['Predicted_Sales'].sum()
                        st.info(f"💡 **AI Insight:** Estimated **{round(total_needed)}** units needed for next 7 days.")
        
        else:
            st.error(f"❌ No sales data for {item} in the last {days_to_consider} days.")
    else:
        st.error(f"❌ Product '{item}' not found in database.")