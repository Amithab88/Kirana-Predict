"""
app.py – Entry point: login + sidebar navigation + page routing.
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

# ── Custom CSS for premium look ───────────────────────────────────────────
st.markdown("""
<style>
/* ─── Import Google Font ─── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

* { font-family: 'Inter', sans-serif; }

/* ─── Sidebar styling ─── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f0c29 0%, #1a1a3e 50%, #24243e 100%);
    border-right: 1px solid rgba(108, 99, 255, 0.2);
}
section[data-testid="stSidebar"] .stRadio > label {
    font-weight: 600;
    color: #b8b5ff;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 0.3rem;
}
section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label {
    background: rgba(255,255,255,0.04);
    border-radius: 10px;
    padding: 0.55rem 0.9rem;
    margin-bottom: 4px;
    transition: all 0.2s ease;
    border: 1px solid transparent;
    font-weight: 400;
    color: #e0e0e0;
}
section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label:hover {
    background: rgba(108, 99, 255, 0.15);
    border-color: rgba(108, 99, 255, 0.3);
    transform: translateX(4px);
}
section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label[data-checked="true"],
section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label[aria-checked="true"] {
    background: linear-gradient(135deg, rgba(108,99,255,0.3), rgba(108,99,255,0.15));
    border-color: #6C63FF;
    font-weight: 600;
    color: #fff;
}

/* ─── Metric cards ─── */
div[data-testid="stMetric"] {
    background: linear-gradient(135deg, #1a1f3c 0%, #252a4a 100%);
    border: 1px solid rgba(108, 99, 255, 0.15);
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 30px rgba(108,99,255,0.2);
    border-color: rgba(108, 99, 255, 0.4);
}
div[data-testid="stMetric"] label { color: #9b97d4 !important; font-size: 0.85rem; letter-spacing: 0.5px; }
div[data-testid="stMetric"] div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; color: #fff !important; }

/* ─── Buttons ─── */
.stButton > button {
    border-radius: 10px;
    font-weight: 500;
    transition: all 0.25s ease;
    border: 1px solid rgba(108, 99, 255, 0.2);
}
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(108, 99, 255, 0.25);
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #6C63FF 0%, #5a52d5 100%);
}

/* ─── Download buttons ─── */
.stDownloadButton > button {
    border-radius: 10px;
    border: 1px solid rgba(108, 99, 255, 0.3);
    background: rgba(108, 99, 255, 0.08);
    transition: all 0.25s ease;
}
.stDownloadButton > button:hover {
    background: rgba(108, 99, 255, 0.18);
    transform: translateY(-2px);
}

/* ─── DataFrames ─── */
div[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(108, 99, 255, 0.12);
}

/* ─── Expanders ─── */
.streamlit-expanderHeader {
    background: rgba(108, 99, 255, 0.06);
    border-radius: 10px;
}

/* ─── Divider ─── */
hr { border-color: rgba(108,99,255,0.12) !important; }

/* ─── Login card ─── */
.login-container {
    max-width: 420px;
    margin: 5vh auto;
    padding: 2.5rem;
    background: linear-gradient(145deg, #1a1f3c, #252a4a);
    border-radius: 20px;
    border: 1px solid rgba(108, 99, 255, 0.2);
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}
.login-title {
    text-align: center;
    font-size: 2rem;
    font-weight: 700;
    background: linear-gradient(135deg, #6C63FF, #b8b5ff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.3rem;
}
.login-subtitle {
    text-align: center;
    color: #888;
    font-size: 0.9rem;
    margin-bottom: 1.5rem;
}

/* ─── Sidebar user card ─── */
.sidebar-user-card {
    background: linear-gradient(135deg, rgba(108,99,255,0.15), rgba(108,99,255,0.05));
    border-radius: 12px;
    padding: 1rem;
    border: 1px solid rgba(108, 99, 255, 0.15);
    text-align: center;
    margin-bottom: 0.5rem;
}
.sidebar-user-card .user-avatar {
    width: 50px;
    height: 50px;
    border-radius: 50%;
    background: linear-gradient(135deg, #6C63FF, #5a52d5);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 1.4rem;
    margin-bottom: 0.5rem;
    box-shadow: 0 4px 15px rgba(108,99,255,0.3);
}
.sidebar-user-card .user-name { font-weight: 600; color: #fff; font-size: 0.9rem; }
.sidebar-user-card .user-role {
    display: inline-block;
    background: rgba(108, 99, 255, 0.2);
    color: #b8b5ff;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 500;
    margin-top: 4px;
    letter-spacing: 0.5px;
}

/* ─── Page header ─── */
.page-header {
    font-size: 1.9rem;
    font-weight: 700;
    background: linear-gradient(135deg, #fff, #b8b5ff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.2rem;
}
.page-breadcrumb {
    font-size: 0.82rem;
    color: #666;
    margin-bottom: 1rem;
}

/* ─── Quick-action card on Home ─── */
.quick-card {
    background: linear-gradient(145deg, #1a1f3c, #252a4a);
    border: 1px solid rgba(108, 99, 255, 0.12);
    border-radius: 14px;
    padding: 1.2rem 1.3rem;
    transition: all 0.25s ease;
    height: 100%;
}
.quick-card:hover {
    border-color: rgba(108, 99, 255, 0.4);
    transform: translateY(-3px);
    box-shadow: 0 8px 25px rgba(108, 99, 255, 0.15);
}
.quick-card .qc-icon { font-size: 1.8rem; margin-bottom: 0.5rem; }
.quick-card .qc-title { font-weight: 600; font-size: 1rem; color: #fff; }
.quick-card .qc-desc  { font-size: 0.82rem; color: #999; margin-top: 4px; }

/* ─── Toast / success flash ─── */
div[data-testid="stToast"] {
    border-radius: 12px;
    border: 1px solid rgba(108, 99, 255, 0.3);
}

/* hidden radio circle dots */
section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label > div:first-child {
    display: none;
}
</style>
""", unsafe_allow_html=True)

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
    st.markdown("""
    <div class="login-container">
        <div class="login-title">📦 Kirana-Predict Pro</div>
        <div class="login-subtitle">Sign in to your dashboard</div>
    </div>
    """, unsafe_allow_html=True)

    col_pad_l, col_login, col_pad_r = st.columns([1.2, 1, 1.2])
    with col_login:
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="you@example.com")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("🔐  Sign In", use_container_width=True):
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
                            time.sleep(0.4)
                            st.rerun()
                        else:
                            st.error(f"❌ {res.get('error', 'Unknown error')}")
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

# ── Build sidebar navigation ─────────────────────────────────────────────
role = st.session_state.user_role
user_initial = (st.session_state.user_email or "?")[0].upper()

# Build page list based on role
NAV_OPTIONS = {}  # {display_label: page_key}

# Analytics section
if role == 'Admin':
    NAV_OPTIONS["📊  Sales Analytics"]    = "Sales Analysis"
    NAV_OPTIONS["📈  Advanced Analytics"] = "Advanced Analytics"
    NAV_OPTIONS["⚖️  Product Comparison"] = "Product Comparison"
NAV_OPTIONS["🔮  AI Forecasting"]         = "Inventory Forecast"

# Inventory section
NAV_OPTIONS["📦  Inventory Dashboard"]    = "Inventory Dashboard"
NAV_OPTIONS["📥  Stock Inward"]           = "Stock Inward"
NAV_OPTIONS["🔄  Store Transfer"]         = "Store Transfer"

# Settings / actions (admin) or Add Sale (staff)
if role == 'Admin':
    NAV_OPTIONS["📧  Alert Settings"]     = "Alert Settings"
    NAV_OPTIONS["🏪  Store Management"]   = "Store Management"
else:
    NAV_OPTIONS["➕  Add New Sale"]        = "Add Sale"

# Reverse lookup for current page → label
page_to_label = {v: k for k, v in NAV_OPTIONS.items()}

_nav = None
_logout = False

with st.sidebar:
    # ─ User card ─
    st.markdown(f"""
    <div class="sidebar-user-card">
        <div class="user-avatar">{user_initial}</div>
        <div class="user-name">{st.session_state.user_email}</div>
        <div class="user-role">{role}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")

    # ─ Home button ─
    if st.button("🏠  Home", use_container_width=True,
                 type=("primary" if st.session_state.page == 'Home' else "secondary"),
                 key="nav_home"):
        _nav = 'Home'

    st.markdown("")

    # ─ Navigation radio ─
    current_label = page_to_label.get(st.session_state.page, None)
    labels = list(NAV_OPTIONS.keys())

    selected_label = st.radio(
        "MODULES",
        labels,
        index=labels.index(current_label) if current_label in labels else None,
        label_visibility="visible",
        key="nav_radio"
    )

    # Detect if user changed selection
    if selected_label and NAV_OPTIONS.get(selected_label) != st.session_state.page:
        _nav = NAV_OPTIONS[selected_label]

    st.markdown("---")

    if st.button("🚪  Sign Out", use_container_width=True, key="nav_logout"):
        _logout = True

    st.markdown("")
    st.caption("© 2026 Kirana-Predict Pro")

# ── Handle navigation & logout AFTER sidebar block closes ────────────────
if _logout:
    db.sign_out()
    for k in ('authenticated', 'user_role', 'user_email'):
        st.session_state[k] = None if k != 'authenticated' else False
    st.rerun()

if _nav is not None:
    ch_page(_nav)
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

elif page == 'Inventory Dashboard':
    inventory_dashboard.render(db)

elif page == 'Stock Inward':
    stock_inward_page.render(db)

elif page == 'Store Transfer':
    store_transfer_page.render(db)

elif page == 'Store Details':
    store_management_page.render_store_details(db)

elif page == 'Add Sale':
    add_sale_page.render(df, db)
