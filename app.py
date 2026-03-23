"""
app.py – Entry point: login + page routing only (~50 lines).
All page logic lives in app/<page>_page.py modules.
"""
import streamlit as st
import pandas as pd
import time
from core.database_manager import load_data_from_db, KiranaDatabase
from app import (
    home_page,
    sales_analysis_page,
    advanced_analytics_page,
    forecasting_page,
    comparison_page,
    alert_settings_page,
    store_management_page,
    add_sale_page,
    inventory_dashboard,
    stock_inward_page,       
    store_transfer_page   
)

# ── Config & shared DB instance ───────────────────────────────────────────
st.set_page_config(page_title="Kirana-Predict Pro", layout="wide", page_icon="📦")
db = KiranaDatabase()

ADMIN_ONLY_PAGES = {
    'Sales Analysis', 'Advanced Analytics', 'Product Comparison',
    'Alert Settings', 'Store Management', 'Store Details', 'Store Comparison'
}

# ── Session state defaults ────────────────────────────────────────────────
for key, default in [('page', 'Home'), ('authenticated', False),
                     ('user_role', None), ('user_email', None)]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Login gate ────────────────────────────────────────────────────────────
if not st.session_state.authenticated:
    st.title("📦 Kirana-Predict Pro")
    st.markdown("**Please log in to access the dashboard.**")
    st.markdown("---")
    col_login, _ = st.columns([1, 1])
    with col_login:
        with st.form("login_form"):
            email = st.text_input("📧 Email", placeholder="you@example.com")
            password = st.text_input("🔑 Password", type="password")
            if st.form_submit_button("🔐 Login", use_container_width=True):
                if not email or not password:
                    st.error("⚠️ Please provide both email and password.")
                else:
                    with st.spinner("Authenticating…"):
                        res = db.authenticate_user(email, password)
                        if res.get("success"):
                            role = db.get_user_role(res["user"].id)
                            st.session_state.update(
                                authenticated=True, user_email=email, user_role=role
                            )
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(f"❌ Login failed: {res.get('error', 'Unknown error')}")
    st.stop()

# ── Data loading ──────────────────────────────────────────────────────────
try:
    df = load_data_from_db()
    if df.empty:
        st.error("❌ No sales data found. Please add data in Supabase.")
        st.stop()
except Exception as e:
    st.error(f"❌ Database error: {e}")
    st.stop()

# Date normalisation
try:
    if 'transaction_date' in df.columns:
        df['transaction_date'] = pd.to_datetime(df['transaction_date'])
    elif 'created_at' in df.columns:
        df['transaction_date'] = pd.to_datetime(df['created_at'])
    else:
        raise KeyError(f"No date column. Columns: {list(df.columns)}")
except Exception as e:
    st.error(f"❌ Date conversion error: {e}")
    st.stop()

# Optional column defaults
if 'store_name'  not in df.columns: df['store_name']  = 'Main Store'
if 'data_source' not in df.columns: df['data_source'] = 'manual'
if 'total_amount' not in df.columns and {'quantity', 'unit_price'}.issubset(df.columns):
    df['total_amount'] = df['quantity'] * df['unit_price']
if 'transaction_id' not in df.columns:
    df['transaction_id'] = [f"TXN_AUTO_{i+1}" for i in range(len(df))]

# ── Navigation helpers ───────────────────────────────────────────────────
def ch_page(name: str):
    st.session_state.page = name

# ── RBAC guard ────────────────────────────────────────────────────────────
def require_admin():
    if st.session_state.user_role != 'Admin':
        st.error("🔒 Access Denied: Admins only.")
        if st.button("⬅️ Return to Home"):
            ch_page('Home'); st.rerun()
        st.stop()

# ── Sidebar navigation ────────────────────────────────────────────────────
role = st.session_state.user_role
with st.sidebar:
    st.markdown("## 📦 Kirana-Predict Pro")
    st.markdown(f"👤 **{st.session_state.user_email}**  \n🔖 Role: `{role}`")
    st.markdown("---")

    st.markdown("### 🏠 Navigation")

    if st.sidebar.button("🏠 Home", use_container_width=True,
                         type=("primary" if st.session_state.page == 'Home' else "secondary"),
                         key="nav_home"):
        ch_page('Home'); st.rerun()

    st.markdown("---")
    st.markdown("### 📊 Analytics")

    if role == 'Admin':
        if st.sidebar.button("📊 Sales Analytics", use_container_width=True,
                             type=("primary" if st.session_state.page == 'Sales Analysis' else "secondary"),
                             key="nav_sales"):
            ch_page('Sales Analysis'); st.rerun()

        if st.sidebar.button("📈 Advanced Analytics", use_container_width=True,
                             type=("primary" if st.session_state.page == 'Advanced Analytics' else "secondary"),
                             key="nav_analytics"):
            ch_page('Advanced Analytics'); st.rerun()

        if st.sidebar.button("⚖️ Product Comparison", use_container_width=True,
                             type=("primary" if st.session_state.page == 'Product Comparison' else "secondary"),
                             key="nav_comparison"):
            ch_page('Product Comparison'); st.rerun()

    if st.sidebar.button("🔮 AI Forecasting", use_container_width=True,
                         type=("primary" if st.session_state.page == 'Inventory Forecast' else "secondary"),
                         key="nav_forecast"):
        ch_page('Inventory Forecast'); st.rerun()

    st.markdown("---")
    st.markdown("### 📦 Inventory")

    if st.sidebar.button("📦 Inventory Dashboard", use_container_width=True,
                         type=("primary" if st.session_state.page == 'Inventory Dashboard' else "secondary"),
                         key="nav_inventory"):
        ch_page('Inventory Dashboard'); st.rerun()

    if st.sidebar.button("📥 Stock Inward", use_container_width=True,
                         type=("primary" if st.session_state.page == 'Stock Inward' else "secondary"),
                         key="nav_stock"):
        ch_page('Stock Inward'); st.rerun()

    if st.sidebar.button("🔄 Store Transfer", use_container_width=True,
                         type=("primary" if st.session_state.page == 'Store Transfer' else "secondary"),
                         key="nav_transfer"):
        ch_page('Store Transfer'); st.rerun()

    if role == 'Admin':
        st.markdown("---")
        st.markdown("### ⚙️ Settings")

        if st.sidebar.button("📧 Alert Settings", use_container_width=True,
                             type=("primary" if st.session_state.page == 'Alert Settings' else "secondary"),
                             key="nav_alerts"):
            ch_page('Alert Settings'); st.rerun()

        if st.sidebar.button("🏪 Store Management", use_container_width=True,
                             type=("primary" if st.session_state.page == 'Store Management' else "secondary"),
                             key="nav_stores"):
            ch_page('Store Management'); st.rerun()

    else:
        st.markdown("---")
        if st.sidebar.button("➕ Add New Sale", use_container_width=True,
                             type=("primary" if st.session_state.page == 'Add Sale' else "secondary"),
                             key="nav_add_sale"):
            ch_page('Add Sale'); st.rerun()

    st.markdown("---")
    if st.sidebar.button("🚪 Logout", use_container_width=True, key="nav_logout"):
        db.sign_out()
        for k in ('authenticated', 'user_role', 'user_email'):
            st.session_state[k] = None if k != 'authenticated' else False
        st.rerun()

# ── Page router ───────────────────────────────────────────────────────────
page = st.session_state.page

if page == 'Home':
    home_page.render(df, ch_page)

elif page == 'Sales Analysis':
    require_admin()
    sales_analysis_page.render(df)

elif page == 'Advanced Analytics':
    require_admin()
    advanced_analytics_page.render(df)

elif page == 'Inventory Forecast':
    forecasting_page.render(df)

elif page == 'Product Comparison':
    require_admin()
    comparison_page.render(df)

elif page == 'Alert Settings':
    require_admin()
    alert_settings_page.render(df)

elif page == 'Store Management':
    require_admin()
    store_management_page.render(db)

elif st.session_state.page == 'Inventory Dashboard':
    inventory_dashboard.render(db)

elif st.session_state.page == 'Stock Inward':
    stock_inward_page.render(db)

elif st.session_state.page == 'Store Transfer':
    store_transfer_page.render(db)
    
elif page == 'Store Details':
    store_management_page.render_store_details(db)

elif page == 'Add Sale':
    add_sale_page.render(df, db)
