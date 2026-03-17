"""
app/add_sale_page.py – Staff manual sale entry page.
Accessible to all logged-in users (Admin and Staff).
"""
import streamlit as st
import pandas as pd
import time
from core.database_manager import KiranaDatabase


def render(df: pd.DataFrame, db: KiranaDatabase):
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
                st.error("❌ Please provide valid Product Name, Quantity (>=1), and Unit Price (>0).")
            else:
                try:
                    # Resolve store_name → store_code
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
                    st.session_state.page = 'Home'
                    st.rerun()

                except Exception as e:
                    st.error(f"Failed to record sale: {e}")
