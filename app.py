import streamlit as st
import pandas as pd
import plotly.express as px
from core.database_manager import load_data_from_db, KiranaDatabase
from core.ml_engine import predict_future_demand
from core.email_manager import EmailAlertManager
from datetime import datetime, timedelta
import time
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

# ============================================
# RBAC HELPER
# ============================================

# Admin-only pages that Staff must not access
ADMIN_ONLY_PAGES = {
    'Sales Analysis', 'Advanced Analytics', 'Product Comparison',
    'Alert Settings', 'Store Management', 'Store Details', 'Store Comparison'
}

def require_admin():
    """Stop rendering and show an error if the current user is not an Admin."""
    if st.session_state.get('user_role') != 'Admin':
        st.error("🔒 Access Denied: This page is for Admins only.")
        st.info("Contact your store manager to request access.")
        if st.button("⬅️ Return to Home"):
            st.session_state.page = 'Home'
            st.rerun()
        st.stop()

# ============================================
# PAGE CONFIG & DB INSTANCE
# ============================================

st.set_page_config(page_title="Kirana-Predict Pro", layout="wide", page_icon="📦")

# Shared database instance (used for auth AND data operations)
db = KiranaDatabase()

# ============================================
# SESSION STATE INIT  (must run before login check)
# ============================================

if 'page' not in st.session_state:
    st.session_state.page = 'Home'
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'user_email' not in st.session_state:
    st.session_state.user_email = None

# ============================================
# LOGIN PAGE  (shown BEFORE any DB data loads)
# ============================================
if not st.session_state.authenticated:
    # Themed login UI
    st.markdown(
        """
        <style>
        .login-header { text-align: center; padding: 2rem 0 1rem; }
        .login-header h1 { font-size: 2.5rem; }
        </style>
        """,
        unsafe_allow_html=True
    )
    st.markdown('<div class="login-header">', unsafe_allow_html=True)
    st.title("📦 Kirana-Predict Pro")
    st.markdown("**Please log in to access the dashboard.**")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    col_login, _ = st.columns([1, 1])
    with col_login:
        with st.form("login_form"):
            email = st.text_input("📧 Email", placeholder="you@example.com")
            password = st.text_input("🔑 Password", type="password", placeholder="Your password")
            submit = st.form_submit_button("🔐 Login", use_container_width=True)

            if submit:
                if not email or not password:
                    st.error("⚠️ Please provide both email and password.")
                else:
                    with st.spinner("Authenticating with Supabase…"):
                        auth_result = db.authenticate_user(email, password)
                        if auth_result.get("success"):
                            user_id = auth_result["user"].id
                            role = db.get_user_role(user_id)

                            st.session_state.authenticated = True
                            st.session_state.user_email = email
                            st.session_state.user_role = role
                            st.success(f"✅ Logged in as **{role}**!  Redirecting…")
                            time.sleep(1)
                            st.rerun()
                        else:
                            err = auth_result.get('error', 'Unknown error')
                            st.error(f"❌ Login failed: {err}")
                            st.caption("Hint: Make sure you have a Supabase Auth account set up.")
    st.stop()  # Nothing else renders until authenticated

# ============================================
# DATA LOADING  (only after successful login)
# ============================================

try:
    df = load_data_from_db()
    if df.empty:
        st.error("❌ No sales data found in database. Please add sales data in Supabase.")
        st.stop()
except Exception as e:
    st.error(f"❌ Database connection failed: {str(e)}")
    st.info("💡 Check your .env file and Supabase credentials")
    st.stop()

try:
    if 'transaction_date' in df.columns:
        df['transaction_date'] = pd.to_datetime(df['transaction_date'])
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

# Normalize optional columns
if 'store_name' not in df.columns:
    df['store_name'] = 'Main Store'
if 'data_source' not in df.columns:
    df['data_source'] = 'manual'
if 'total_amount' not in df.columns and 'quantity' in df.columns and 'unit_price' in df.columns:
    df['total_amount'] = df['quantity'] * df['unit_price']
if 'transaction_id' not in df.columns:
    df['transaction_id'] = [f"TXN_AUTO_{i+1}" for i in range(len(df))]

# 2. Function to change pages
def ch_page(page_name):
    st.session_state.page = page_name

# 3. Top Navigation Bar & Logout
col_nav, col_logout = st.columns([4, 1])

with col_nav:
    if st.session_state.page != 'Home':
        if st.button("⬅️ Back to Home"):
            ch_page('Home')
            st.rerun()

with col_logout:
    st.markdown(f"👤 **{st.session_state.user_email}** ({st.session_state.user_role})")
    if st.button("Logout"):
        db.sign_out()
        st.session_state.authenticated = False
        st.session_state.user_role = None
        st.session_state.user_email = None
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
        if st.session_state.user_role == 'Admin':
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
        
        if st.session_state.user_role == 'Admin':
            st.subheader("⚖️ Product Comparison")
            st.info("📊 Compare 2-4 products side-by-side.")
            if st.button("Open Product Comparison", use_container_width=True, type="primary", key="btn_comparison"):
                ch_page('Product Comparison')
                st.rerun()
    
    # Row 3: Alerts & Store Management (Only for Admin)
    if st.session_state.user_role == 'Admin':
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
    else:
        st.info("🔒 Contact your Admin to access Alert Settings or Store Management.")
    
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
# SALES ANALYSIS PAGE  [Admin only]
# ============================================
elif st.session_state.page == 'Sales Analysis':
    require_admin()
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
# ADVANCED ANALYTICS DASHBOARD  [Admin only]
# ============================================
elif st.session_state.page == 'Advanced Analytics':
    require_admin()
    st.title("📈 Advanced Analytics Dashboard")
    st.markdown("### Deep Business Insights & Performance Metrics")
    
    # Date filter for analytics
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
    
    if len(analytics_date_range) == 2:
        start_date_an = pd.to_datetime(analytics_date_range[0])
        end_date_an = pd.to_datetime(analytics_date_range[1])
        df_analytics = df[(df['transaction_date'] >= start_date_an) & (df['transaction_date'] <= end_date_an)].copy()
        
        if df_analytics.empty:
            st.warning("⚠️ No data in selected period")
            st.stop()
        
        # SECTION 1: KEY METRICS OVERVIEW
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
        
        # SECTION 2: REVENUE TREND ANALYSIS
        st.markdown("---")
        st.subheader("📈 Revenue Trend Analysis")
        
        trend_col1, trend_col2 = st.columns([2, 1])
        
        with trend_col1:
            daily_revenue = df_analytics.groupby(df_analytics['transaction_date'].dt.date)['total_amount'].sum().reset_index()
            daily_revenue.columns = ['Date', 'Revenue']
            
            fig_revenue_trend = px.line(
                daily_revenue,
                x='Date',
                y='Revenue',
                title='Daily Revenue Trend',
                markers=True
            )
            fig_revenue_trend.update_traces(line_color='#2E86AB', line_width=3, marker=dict(size=6))
            fig_revenue_trend.update_layout(
                hovermode='x unified',
                yaxis_title='Revenue (₹)',
                xaxis_title='Date'
            )
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
        
        # SECTION 3: PRODUCT PERFORMANCE
        st.markdown("---")
        st.subheader("🏆 Product Performance Analysis")
        
        perf_col1, perf_col2 = st.columns(2)
        
        product_revenue = df_analytics.groupby('product_name')['total_amount'].sum().sort_values(ascending=False)
        
        with perf_col1:
            st.markdown("**🥇 Top 5 Revenue Generators**")
            top_5 = product_revenue.head(5)
            
            fig_top5 = px.bar(
                x=top_5.values,
                y=top_5.index,
                orientation='h',
                title='Top 5 Products by Revenue',
                color=top_5.values,
                color_continuous_scale='Greens'
            )
            fig_top5.update_layout(
                xaxis_title='Revenue (₹)',
                yaxis_title='',
                showlegend=False,
                height=300
            )
            st.plotly_chart(fig_top5, use_container_width=True)
        
        with perf_col2:
            st.markdown("**⚠️ Bottom 5 Performers**")
            bottom_5 = product_revenue.tail(5).sort_values()
            
            fig_bottom5 = px.bar(
                x=bottom_5.values,
                y=bottom_5.index,
                orientation='h',
                title='Bottom 5 Products by Revenue',
                color=bottom_5.values,
                color_continuous_scale='Reds'
            )
            fig_bottom5.update_layout(
                xaxis_title='Revenue (₹)',
                yaxis_title='',
                showlegend=False,
                height=300
            )
            st.plotly_chart(fig_bottom5, use_container_width=True)
        
        # SECTION 4: SALES DISTRIBUTION
        st.markdown("---")
        st.subheader("🥧 Sales Distribution Analysis")
        
        dist_col1, dist_col2 = st.columns([1.5, 1])
        
        with dist_col1:
            product_quantity = df_analytics.groupby('product_name')['quantity'].sum().head(8)
            
            fig_pie = px.pie(
                values=product_quantity.values,
                names=product_quantity.index,
                title='Product Sales Distribution (Top 8)',
                hole=0.4
            )
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
        
        # SECTION 5: TIME-BASED ANALYSIS
        st.markdown("---")
        st.subheader("📅 Time-Based Sales Patterns")
        
        time_col1, time_col2 = st.columns(2)
        
        with time_col1:
            df_analytics['day_of_week'] = df_analytics['transaction_date'].dt.day_name()
            day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            
            dow_sales = df_analytics.groupby('day_of_week')['total_amount'].sum().reindex(day_order).fillna(0)
            
            fig_dow = px.bar(
                x=dow_sales.index,
                y=dow_sales.values,
                title='Sales by Day of Week',
                color=dow_sales.values,
                color_continuous_scale='Blues',
                labels={'x': 'Day', 'y': 'Revenue (₹)'}
            )
            fig_dow.update_layout(showlegend=False)
            st.plotly_chart(fig_dow, use_container_width=True)
        
        with time_col2:
            df_analytics['month'] = df_analytics['transaction_date'].dt.to_period('M').astype(str)
            monthly_sales = df_analytics.groupby('month')['total_amount'].sum()
            
            if len(monthly_sales) > 1:
                fig_monthly = px.line(
                    x=monthly_sales.index,
                    y=monthly_sales.values,
                    title='Monthly Revenue Trend',
                    markers=True
                )
                fig_monthly.update_traces(line_color='#F77F00', line_width=3, marker=dict(size=8))
                fig_monthly.update_layout(
                    xaxis_title='Month',
                    yaxis_title='Revenue (₹)'
                )
                st.plotly_chart(fig_monthly, use_container_width=True)
            else:
                st.info("📊 Need data from multiple months for monthly trend analysis")
        
        # SECTION 6: STORE PERFORMANCE (if multi-store)
        if df_analytics['store_name'].nunique() > 1:
            st.markdown("---")
            st.subheader("🏪 Store Performance Comparison")
            
            store_revenue = df_analytics.groupby('store_name').agg({
                'total_amount': 'sum',
                'quantity': 'sum',
                'transaction_id': 'count'
            }).round(2)
            store_revenue.columns = ['Revenue', 'Units Sold', 'Transactions']
            store_revenue = store_revenue.sort_values('Revenue', ascending=False)
            
            store_col1, store_col2 = st.columns([1.5, 1])
            
            with store_col1:
                fig_store = px.bar(
                    store_revenue,
                    x=store_revenue.index,
                    y='Revenue',
                    title='Revenue by Store',
                    color='Revenue',
                    color_continuous_scale='Teal'
                )
                fig_store.update_layout(showlegend=False, xaxis_title='Store', yaxis_title='Revenue (₹)')
                st.plotly_chart(fig_store, use_container_width=True)
            
            with store_col2:
                st.markdown("**🏆 Store Rankings**")
                store_revenue_display = store_revenue.copy()
                store_revenue_display['Revenue'] = store_revenue_display['Revenue'].apply(lambda x: f"₹{x:,.0f}")
                st.dataframe(store_revenue_display, use_container_width=True, height=300)
        
        # SECTION 7: EXPORT ANALYTICS
        st.markdown("---")
        st.subheader("📥 Export Analytics Report")
        
        export_col1, export_col2, export_col3 = st.columns(3)
        
        analytics_report = pd.DataFrame({
            'Metric': [
                'Total Revenue',
                'Total Transactions',
                'Total Units Sold',
                'Unique Products',
                'Average Transaction Value',
                'Best Selling Product',
                'Highest Revenue Product',
                'Analysis Period'
            ],
            'Value': [
                f"₹{total_revenue:,.2f}",
                total_transactions,
                total_units,
                unique_products,
                f"₹{avg_transaction:.2f}",
                df_analytics.groupby('product_name')['quantity'].sum().idxmax(),
                product_revenue.idxmax(),
                f"{start_date_an.strftime('%d %b %Y')} - {end_date_an.strftime('%d %b %Y')}"
            ]
        })
        
        with export_col1:
            report_csv, report_csv_name = export_to_csv(analytics_report, "analytics_summary")
            st.download_button(
                "📊 Summary Report (CSV)",
                data=report_csv,
                file_name=report_csv_name,
                mime="text/csv",
                use_container_width=True
            )
        
        with export_col2:
            product_perf_csv, product_perf_name = export_to_csv(
                df_analytics.groupby('product_name').agg({
                    'quantity': 'sum',
                    'total_amount': 'sum',
                    'transaction_id': 'count'
                }).reset_index(),
                "product_performance"
            )
            st.download_button(
                "🛒 Product Performance (CSV)",
                data=product_perf_csv,
                file_name=product_perf_name,
                mime="text/csv",
                use_container_width=True
            )
        
        with export_col3:
            daily_report_csv, daily_report_name = export_to_csv(daily_revenue, "daily_revenue")
            st.download_button(
                "📅 Daily Revenue (CSV)",
                data=daily_report_csv,
                file_name=daily_report_name,
                mime="text/csv",
                use_container_width=True
            )

# ============================================
# PRODUCT COMPARISON PAGE  [Admin only]
# ============================================
elif st.session_state.page == 'Product Comparison':
    require_admin()
    st.title("⚖️ Multi-Product Comparison")
    st.markdown("### Compare sales performance across multiple products")
    
    st.markdown("---")
    
    # Product selection
    st.subheader("🛒 Select Products to Compare")
    
    all_products = sorted(df['product_name'].unique().tolist())
    
    if len(all_products) < 2:
        st.error("❌ Need at least 2 products in database for comparison")
        st.stop()
    
    col_select1, col_select2 = st.columns(2)
    
    with col_select1:
        num_products = st.slider(
            "How many products to compare?",
            min_value=2,
            max_value=min(4, len(all_products)),
            value=2,
            help="Select 2-4 products for comparison"
        )
    
    with col_select2:
        st.info(f"📦 {len(all_products)} products available in database")
    
    # Create product selectors dynamically
    st.markdown("---")
    st.markdown("**Select Products:**")
    
    selected_products = []
    cols = st.columns(num_products)
    
    for i in range(num_products):
        with cols[i]:
            # Filter out already selected products
            available = [p for p in all_products if p not in selected_products]
            
            if available:
                product = st.selectbox(
                    f"Product {i+1}",
                    available,
                    key=f"product_select_{i}"
                )
                selected_products.append(product)
            else:
                st.warning("No more products available")
    
    if len(selected_products) < 2:
        st.warning("⚠️ Please select at least 2 products to compare")
        st.stop()
    
    # Date range filter
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
        st.stop()
    
    start_date_comp = pd.to_datetime(comparison_dates[0])
    end_date_comp = pd.to_datetime(comparison_dates[1])
    
    # Filter data for selected products and date range
    comparison_df = df[
        (df['product_name'].isin(selected_products)) &
        (df['transaction_date'] >= start_date_comp) &
        (df['transaction_date'] <= end_date_comp)
    ]
    
    if comparison_df.empty:
        st.warning("⚠️ No sales data found for selected products in this period")
        st.stop()
    
    # SECTION 1: SUMMARY METRICS COMPARISON
    st.markdown("---")
    st.subheader("📊 Performance Summary")
    
    metrics_data = []
    
    for product in selected_products:
        product_df = comparison_df[comparison_df['product_name'] == product]
        
        total_revenue = product_df['total_amount'].sum()
        total_units = product_df['quantity'].sum()
        total_transactions = len(product_df)
        avg_price = product_df['unit_price'].mean()
        
        metrics_data.append({
            'Product': product,
            'Revenue': f"₹{total_revenue:,.0f}",
            'Units Sold': f"{total_units:,}",
            'Transactions': total_transactions,
            'Avg Price': f"₹{avg_price:.2f}"
        })
    
    metrics_table = pd.DataFrame(metrics_data)
    
    st.dataframe(
        metrics_table,
        use_container_width=True,
        hide_index=True,
        height=150
    )
    
    # SECTION 2: REVENUE COMPARISON BAR CHART
    st.markdown("---")
    st.subheader("💰 Revenue Comparison")
    
    revenue_comparison = comparison_df.groupby('product_name')['total_amount'].sum().sort_values(ascending=False)
    
    fig_revenue_comp = px.bar(
        x=revenue_comparison.index,
        y=revenue_comparison.values,
        title='Total Revenue by Product',
        color=revenue_comparison.values,
        color_continuous_scale='Blues',
        labels={'x': 'Product', 'y': 'Revenue (₹)'}
    )
    fig_revenue_comp.update_layout(showlegend=False, height=400)
    st.plotly_chart(fig_revenue_comp, use_container_width=True)
    
    winner = revenue_comparison.idxmax()
    winner_revenue = revenue_comparison.max()
    st.success(f"🏆 **Top Revenue Generator:** {winner} with ₹{winner_revenue:,.2f}")
    
    # SECTION 3: SALES TRENDS COMPARISON
    st.markdown("---")
    st.subheader("📈 Sales Trends Over Time")
    
    daily_comparison = comparison_df.groupby(
        [comparison_df['transaction_date'].dt.date, 'product_name']
    )['quantity'].sum().reset_index()
    daily_comparison.columns = ['Date', 'Product', 'Quantity']
    daily_comparison['Date'] = pd.to_datetime(daily_comparison['Date'])
    
    fig_trends = px.line(
        daily_comparison,
        x='Date',
        y='Quantity',
        color='Product',
        title='Daily Sales Trends Comparison',
        markers=True
    )
    fig_trends.update_layout(
        hovermode='x unified',
        yaxis_title='Units Sold',
        height=450
    )
    st.plotly_chart(fig_trends, use_container_width=True)
    
    # SECTION 4: UNITS SOLD COMPARISON
    st.markdown("---")
    st.subheader("📦 Volume Comparison")
    
    col_units1, col_units2 = st.columns([1.5, 1])
    
    with col_units1:
        units_comparison = comparison_df.groupby('product_name')['quantity'].sum().sort_values(ascending=False)
        
        fig_units = px.bar(
            x=units_comparison.index,
            y=units_comparison.values,
            title='Total Units Sold',
            color=units_comparison.values,
            color_continuous_scale='Greens',
            labels={'x': 'Product', 'y': 'Units Sold'}
        )
        fig_units.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig_units, use_container_width=True)
    
    with col_units2:
        st.markdown("**📊 Volume Rankings**")
        
        volume_rank = pd.DataFrame({
            'Rank': range(1, len(units_comparison) + 1),
            'Product': units_comparison.index,
            'Units': units_comparison.values
        })
        st.dataframe(volume_rank, use_container_width=True, hide_index=True, height=350)
    
    # SECTION 5: GROWTH ANALYSIS
    st.markdown("---")
    st.subheader("📊 Growth Analysis")
    
    growth_data = []
    
    for product in selected_products:
        product_daily = daily_comparison[daily_comparison['Product'] == product].copy()
        product_daily = product_daily.sort_values('Date')
        
        if len(product_daily) > 1:
            mid_point = len(product_daily) // 2
            first_half = product_daily.head(mid_point)['Quantity'].sum()
            second_half = product_daily.tail(len(product_daily) - mid_point)['Quantity'].sum()
            
            if first_half > 0:
                growth_rate = ((second_half - first_half) / first_half) * 100
            else:
                growth_rate = 0
            
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
    
    # SECTION 6: PRICE ANALYSIS
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
        total_revenue = product_df['total_amount'].sum()
        total_units = product_df['quantity'].sum()
        revenue_per_unit = total_revenue / total_units if total_units > 0 else 0
        
        price_efficiency.append({
            'Product': product,
            'Revenue per Unit': f"₹{revenue_per_unit:.2f}"
        })
    
    st.markdown("**💡 Revenue Efficiency:**")
    st.dataframe(pd.DataFrame(price_efficiency), use_container_width=True, hide_index=True)
    
    # SECTION 7: EXPORT COMPARISON REPORT
    st.markdown("---")
    st.subheader("📥 Export Comparison Report")
    
    exp_col1, exp_col2, exp_col3 = st.columns(3)
    
    comparison_report = comparison_df.copy()
    comparison_report['Date'] = comparison_report['transaction_date'].dt.strftime('%Y-%m-%d')
    comparison_report = comparison_report[['Date', 'product_name', 'quantity', 'unit_price', 'total_amount', 'store_name']]
    
    with exp_col1:
        comp_csv, comp_csv_name = export_to_csv(
            comparison_report,
            f"product_comparison_{len(selected_products)}_products"
        )
        st.download_button(
            "📊 Full Comparison Data (CSV)",
            data=comp_csv,
            file_name=comp_csv_name,
            mime="text/csv",
            use_container_width=True
        )
    
    with exp_col2:
        summary_csv, summary_csv_name = export_to_csv(metrics_table, "comparison_summary")
        st.download_button(
            "📋 Summary Report (CSV)",
            data=summary_csv,
            file_name=summary_csv_name,
            mime="text/csv",
            use_container_width=True
        )
    
    with exp_col3:
        if growth_data:
            growth_csv, growth_csv_name = export_to_csv(
                pd.DataFrame(growth_data),
                "growth_analysis"
            )
            st.download_button(
                "📈 Growth Analysis (CSV)",
                data=growth_csv,
                file_name=growth_csv_name,
                mime="text/csv",
                use_container_width=True
            )
    
    # INSIGHTS & RECOMMENDATIONS
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

# ============================================
# ALERT SETTINGS PAGE (Feature 5)  [Admin only]
# ============================================
elif st.session_state.page == 'Alert Settings':
    require_admin()
    st.title("📧 Email Alert Settings")
    st.markdown("### Configure automated notifications and reports")
    
    email_manager = EmailAlertManager()
    
    # Status check
    st.markdown("---")
    st.subheader("📊 System Status")
    
    status_col1, status_col2, status_col3 = st.columns(3)
    
    with status_col1:
        if email_manager.enabled:
            st.success("✅ Email Alerts ENABLED")
        else:
            st.error("❌ Email Alerts DISABLED")
    
    with status_col2:
        st.info(f"📮 Service: {email_manager.service.upper()}")
    
    with status_col3:
        st.info(f"📧 Recipients: {len(email_manager.recipients)}")
    
    if not email_manager.enabled:
        st.warning("⚠️ **Email alerts are currently disabled.** Add email configuration to Streamlit Secrets to enable.")
        
        with st.expander("📖 **Setup Instructions**"):
            st.markdown("""
            ### Gmail Setup (5 minutes):
            
            1. Enable 2-Factor Authentication on your Gmail
            2. Create an App Password at https://myaccount.google.com/apppasswords
            3. Add these to Streamlit Cloud → Settings → Secrets:
```toml
            EMAIL_ENABLED = "true"
            EMAIL_SERVICE = "gmail"
            SMTP_SERVER = "smtp.gmail.com"
            SMTP_PORT = "587"
            EMAIL_SENDER = "your-email@gmail.com"
            EMAIL_PASSWORD = "your-16-char-app-password"
            EMAIL_RECIPIENTS = "recipient@email.com"
```
            
            4. Reboot your app
            """)
    
    # Configuration display
    st.markdown("---")
    st.subheader("⚙️ Current Configuration")
    
    config_data = {
        'Setting': ['Service', 'Sender Email', 'Recipients', 'Status'],
        'Value': [
            email_manager.service,
            email_manager.sender if email_manager.sender else 'Not configured',
            ', '.join(email_manager.recipients) if email_manager.recipients else 'Not configured',
            'Active' if email_manager.enabled else 'Inactive'
        ]
    }
    
    st.dataframe(pd.DataFrame(config_data), use_container_width=True, hide_index=True)
    
    # Alert Types
    st.markdown("---")
    st.subheader("🔔 Available Alert Types")
    
    alert_types = [
        ['Alert Type', 'Trigger', 'Frequency', 'Status'],
        ['Critical Stock', 'Inventory < 3 days', 'Immediate', '🟢 Active' if email_manager.enabled else '🔴 Inactive'],
        ['Low Stock Warning', 'Inventory < 7 days', 'Daily', '🟢 Active' if email_manager.enabled else '🔴 Inactive'],
        ['Daily Summary', 'End of day', 'Daily 6PM', '🟡 Manual'],
        ['Weekly Report', 'Performance metrics', 'Monday 9AM', '🟡 Manual']
    ]
    
    st.dataframe(
        pd.DataFrame(alert_types[1:], columns=alert_types[0]),
        use_container_width=True,
        hide_index=True
    )
    
    if email_manager.enabled:
        st.markdown("---")
        st.subheader("🧪 Test Email Alerts")
        
        test_col1, test_col2 = st.columns(2)
        
        with test_col1:
            st.markdown("**Test Low Stock Alert:**")
            
            test_product = st.selectbox(
                "Select Product",
                df['product_name'].unique().tolist(),
                key="test_product_alert"
            )
            
            test_stock = st.number_input("Current Stock", min_value=0, value=10, key="test_stock")
            test_daily_sales = st.number_input("Avg Daily Sales", min_value=0.1, value=5.0, step=0.1, key="test_daily")
            
            if st.button("📧 Send Test Low Stock Alert", use_container_width=True):
                days_remaining = test_stock / test_daily_sales if test_daily_sales > 0 else 0
                
                html = email_manager.create_low_stock_alert(
                    product_name=test_product,
                    current_stock=test_stock,
                    days_remaining=days_remaining,
                    avg_daily_sales=test_daily_sales
                )
                
                urgency = "CRITICAL TEST" if days_remaining < 3 else "LOW STOCK TEST"
                subject = f"🧪 {urgency}: {test_product} - {days_remaining:.1f} days"
                
                with st.spinner('Sending email...'):
                    success = email_manager.send_email(subject, html)
                
                if success:
                    st.success("✅ Test email sent successfully! Check your inbox.")
                else:
                    st.error("❌ Email send failed. Check configuration.")
        
        with test_col2:
            st.markdown("**Test Daily Summary:**")
            
            summary_date = st.date_input(
                "Summary Date",
                value=datetime.now().date(),
                key="summary_date"
            )
            
            st.info(f"Will send summary for {summary_date.strftime('%d %b %Y')}")
            
            if st.button("📊 Send Test Daily Summary", use_container_width=True):
                summary_df = df[df['transaction_date'].dt.date == summary_date]
                
                if summary_df.empty:
                    st.warning(f"⚠️ No sales data for {summary_date}")
                else:
                    html = email_manager.create_daily_summary(summary_df)
                    subject = f"📊 TEST Daily Summary - {summary_date.strftime('%d %b %Y')}"
                    
                    with st.spinner('Sending email...'):
                        success = email_manager.send_email(subject, html)
                    
                    if success:
                        st.success("✅ Test summary sent! Check your inbox.")
                    else:
                        st.error("❌ Email send failed.")
        
        # Check Inventory & Send Alerts
        st.markdown("---")
        st.subheader("🚨 Run Stock Alert Check")
        
        st.info("This will check all products and send alerts for any items with low stock.")
        
        lookback_days = st.slider("Lookback Period (days)", 7, 90, 30, key="alert_lookback")
        
        if st.button("🔍 Check Inventory & Send Alerts", type="primary", use_container_width=True):
            with st.spinner('Analyzing inventory...'):
                inventory_alerts = []
                
                for product in df['product_name'].unique():
                    product_df = df[df['product_name'] == product]
                    
                    cutoff_date = datetime.now() - timedelta(days=lookback_days)
                    recent = product_df[product_df['transaction_date'] >= cutoff_date]
                    
                    if not recent.empty:
                        avg_daily = recent['quantity'].sum() / recent['transaction_date'].nunique()
                        
                        current_stock = int(avg_daily * 30)
                        days_remaining = current_stock / avg_daily if avg_daily > 0 else 999
                        
                        if days_remaining < 7:
                            inventory_alerts.append({
                                'product_name': product,
                                'current_stock': current_stock,
                                'days_remaining': days_remaining,
                                'avg_daily_sales': avg_daily
                            })
                
                if inventory_alerts:
                    st.warning(f"⚠️ Found {len(inventory_alerts)} product(s) with low stock!")
                    
                    alert_df = pd.DataFrame(inventory_alerts)
                    alert_df['Days Left'] = alert_df['days_remaining'].round(1)
                    alert_df = alert_df[['product_name', 'current_stock', 'Days Left', 'avg_daily_sales']]
                    alert_df.columns = ['Product', 'Stock', 'Days Left', 'Avg Daily Sales']
                    
                    st.dataframe(alert_df, use_container_width=True, hide_index=True)
                    
                    alerts_sent = email_manager.send_low_stock_alerts(inventory_alerts)
                    
                    if alerts_sent > 0:
                        st.success(f"✅ Sent {alerts_sent} alert email(s)!")
                    else:
                        st.error("❌ Failed to send alerts")
                else:
                    st.success("✅ All products have healthy stock levels!")
    
    # Tips
    st.markdown("---")
    st.subheader("💡 Alert Best Practices")
    
    with st.expander("📖 **View Tips**"):
        st.markdown("""
        ### Recommended Alert Strategy:
        
        **Critical Alerts (< 3 days):**
        - Send immediately when detected
        - Include mobile numbers if using SMS
        - Escalate to manager
        
        **Warning Alerts (< 7 days):**
        - Daily check at 9 AM
        - Group multiple products in one email
        - Include reorder recommendations
        
        **Daily Summaries:**
        - Send at 6 PM after business hours
        - Include top 5 products and total revenue
        - Highlight unusual patterns
        
        **Weekly Reports:**
        - Send Monday 9 AM for planning
        - Include growth trends
        - Compare week-over-week performance
        
        ### Email Deliverability Tips:
        - Use professional sender email
        - Avoid spam trigger words
        - Keep subject lines clear
        - Test with small recipient list first
        - Monitor bounce rates
        """)

# ============================================
# STORE MANAGEMENT PAGE (PHASE 3)
# ============================================
# STORE MANAGEMENT PAGE  [Admin only]
# ============================================
elif st.session_state.page == 'Store Management':
    require_admin()
    st.title("🏪 Multi-Store Management")
    st.markdown("---")
    
    # Store Summary Cards
    stores_df = db.get_all_stores()
    store_perf = db.get_store_performance()
    
    # Initialize active_stores early so it's always defined
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
    
    # ============================================
    # TABS SECTION - THIS IS THE KEY PART!
    # ============================================
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
            # Display stores as cards
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
                        # Get performance for this store
                        if not store_perf.empty:
                            perf = store_perf[store_perf['store_code'] == store['store_code']]
                            if not perf.empty:
                                st.metric("Revenue", f"₹{perf.iloc[0]['total_revenue']:,.0f}")
                                st.metric("Transactions", f"{perf.iloc[0]['total_transactions']:,}")
                    
                    # Action buttons
                    col_a, col_b, col_c = st.columns(3)
                    
                    with col_a:
                        if st.button(f"View Details", key=f"view_{store['store_code']}"):
                            st.session_state['selected_store'] = store['store_code']
                            ch_page('Store Details')
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
                    
                    # Edit form (shown when Edit is clicked)
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
                store_code = st.text_input(
                    "Store Code *", 
                    placeholder="e.g., STORE005",
                    help="Unique identifier (e.g., STORE005)"
                )
                store_name = st.text_input(
                    "Store Name *", 
                    placeholder="e.g., Chennai Branch"
                )
                city = st.text_input("City *", placeholder="e.g., Chennai")
            
            with col2:
                state = st.text_input("State *", placeholder="e.g., Tamil Nadu")
                pos_system = st.text_input(
                    "POS System", 
                    placeholder="e.g., Petpooja, Square, Custom"
                )
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
            # Performance Table
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
            
            # Revenue Chart
            st.markdown("---")
            st.subheader("💰 Revenue by Store")
            
            fig_revenue = px.bar(
                store_perf,
                x='store_name',
                y='total_revenue',
                color='city',
                title="Total Revenue by Store",
                labels={'total_revenue': 'Revenue (₹)', 'store_name': 'Store'}
            )
            st.plotly_chart(fig_revenue, use_container_width=True)
            
            # Transaction Volume
            st.markdown("---")
            st.subheader("📦 Transaction Volume")
            
            fig_trans = px.bar(
                store_perf,
                x='store_name',
                y='total_transactions',
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
            # Select stores to compare
            store_options = active_stores['store_name'].tolist()
            selected_stores = st.multiselect(
                "Select 2-4 stores to compare:",
                options=store_options,
                default=store_options[:2] if len(store_options) >= 2 else store_options
            )
            
            if len(selected_stores) >= 2:
                # Get store codes
                selected_codes = active_stores[
                    active_stores['store_name'].isin(selected_stores)
                ]['store_code'].tolist()
                
                # Get sales data
                comparison_data = []
                for code in selected_codes:
                    store_sales = db.get_sales_by_store(code)
                    if not store_sales.empty:
                        comparison_data.append({
                            'store_code': code,
                            'store_name': active_stores[active_stores['store_code'] == code].iloc[0]['store_name'],
                            'total_revenue': store_sales['total'].sum(),
                            'total_quantity': store_sales['quantity'].sum(),
                            'transactions': len(store_sales),
                            'unique_products': store_sales['product_name'].nunique()
                        })
                
                if comparison_data:
                    comp_df = pd.DataFrame(comparison_data)
                    
                    # Comparison metrics
                    cols = st.columns(len(selected_stores))
                    for idx, row in comp_df.iterrows():
                        with cols[idx]:
                            st.metric(row['store_name'], f"₹{row['total_revenue']:,.0f}")
                            st.write(f"📦 {row['transactions']:,} transactions")
                            st.write(f"🛍️ {row['unique_products']} products")
                    
                    # Side-by-side charts
                    st.markdown("---")
                    
                    fig_comp = px.bar(
                        comp_df,
                        x='store_name',
                        y=['total_revenue', 'total_quantity'],
                        barmode='group',
                        title="Revenue & Quantity Comparison"
                    )
                    st.plotly_chart(fig_comp, use_container_width=True)
            else:
                st.info("Please select at least 2 stores to compare.")
        else:
            st.warning("You need at least 2 active stores to use this feature.")


# ============================================
# STORE DETAILS PAGE
# ============================================
elif st.session_state.page == 'Store Details':
    if 'selected_store' not in st.session_state:
        st.warning("No store selected!")
        if st.button("← Back to Store Management"):
            ch_page('Store Management')
            st.rerun()
    else:
        store_code = st.session_state['selected_store']
        store = db.get_store_by_code(store_code)
        
        if not store:
            st.error("Store not found!")
        else:
            # Header
            col1, col2 = st.columns([3, 1])
            with col1:
                st.title(f"🏪 {store['store_name']}")
                st.caption(f"{store['city']}, {store['state']}")
            with col2:
                if st.button("← Back"):
                    ch_page('Store Management')
                    st.rerun()
            
            st.markdown("---")
            
            # Store Info
            col1, col2, col3 = st.columns(3)
            col1.metric("Store Code", store['store_code'])
            col2.metric("Status", "✅ Active" if store['is_active'] else "❌ Inactive")
            col3.metric("POS System", store.get('pos_system', 'N/A'))
            
            st.markdown("---")
            
            # Get store performance
            store_sales = db.get_sales_by_store(store_code)
            
            if not store_sales.empty:
                # KPIs
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Revenue", f"₹{store_sales['total'].sum():,.0f}")
                col2.metric("Transactions", f"{len(store_sales):,}")
                col3.metric("Products Sold", f"{store_sales['quantity'].sum():,}")
                col4.metric("Avg Transaction", f"₹{store_sales['total'].mean():,.2f}")
                
                st.markdown("---")
                
                # Tabs
                tab1, tab2, tab3 = st.tabs([
                    "📈 Sales Trend",
                    "🏆 Top Products",
                    "📊 Detailed Data"
                ])
                
                with tab1:
                    st.subheader("30-Day Sales Trend")
                    trend = db.get_store_sales_trend(store_code, days=30)
                    if not trend.empty:
                        fig = px.line(
                            trend,
                            x='date',
                            y='revenue',
                            title="Daily Revenue",
                            labels={'revenue': 'Revenue (₹)', 'date': 'Date'}
                        )
                        st.plotly_chart(fig, use_container_width=True)
                
                with tab2:
                    st.subheader("Top 10 Products")
                    top_products = db.get_store_product_performance(store_code).head(10)
                    if not top_products.empty:
                        fig = px.bar(
                            top_products,
                            x='product_name',
                            y='revenue',
                            title="Revenue by Product",
                            labels={'revenue': 'Revenue (₹)'}
                        )
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
                    
                    # Export
                    csv = store_sales.to_csv(index=False)
                    st.download_button(
                        "📥 Download Store Data (CSV)",
                        csv,
                        file_name=f"{store_code}_sales_data.csv",
                        mime="text/csv"
                    )
            else:
                st.info(f"No sales data available for {store['store_name']} yet.")
# Placeholder Store Details page (for future deep-dive views)
elif st.session_state.page == 'Store Details':
    st.title("🏪 Store Details")
    st.info("Detailed store view coming soon.")

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

# ============================================
# ADD SALE PAGE (STAFF / MANUAL ENTRY)
# ============================================
elif st.session_state.page == 'Add Sale':
    st.title("➕ Add New Sale")
    st.markdown("Manually record a transaction into the database.")
    
    with st.form("manual_sale_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            product_name = st.text_input("Product Name *", placeholder="e.g., Aashirvaad Atta 5kg")
            quantity = st.number_input("Quantity *", min_value=1, step=1)
            unit_price = st.number_input("Unit Price (₹) *", min_value=0.0, step=0.5)
            
        with col2:
            if 'store_name' in df.columns:
                all_stores = sorted(df['store_name'].dropna().unique().tolist())
            else:
                all_stores = ['Main Store']
            store_name = st.selectbox("Store", all_stores)
            category = st.text_input("Category", placeholder="e.g., Groceries")
            
        submitted = st.form_submit_button("Submit Sale", type="primary")
        
        if submitted:
            if not product_name or quantity <= 0 or unit_price <= 0:
                st.error("❌ Please provide valid Product Name, Quantity (>=1), and Unit Price (>=0).")
            else:
                try:
                    # In a real app we'd map store_name -> store_code. For now just passing store_name
                    # or creating a dummy store code. Let's get the code if possible:
                    store_code_val = "STORE_UNKNOWN"
                    stores_df = db.get_all_stores()
                    if not stores_df.empty:
                        matched = stores_df[stores_df['store_name'] == store_name]
                        if not matched.empty:
                            store_code_val = matched.iloc[0]['store_code']
                            
                    sale_data = {
                        "product_name": product_name,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "store_code": store_code_val,
                        "total_amount": quantity * unit_price,
                        "category": category if category else "Uncategorized"
                    }
                    
                    db.add_sale(sale_data, source='manual_entry')
                    st.success(f"✅ Sale of {quantity} x {product_name} recorded successfully!")
                    st.balloons()
                    time.sleep(1.5)
                    ch_page('Home')
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to record sale: {e}")