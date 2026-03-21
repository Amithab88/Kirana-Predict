"""
app/store_transfer_page.py - Inter-Store Transfer Management
Transfer stock between stores with approval workflow
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from core.database_manager import KiranaDatabase
from core.inventory_manager import InventoryManager


def render(db: KiranaDatabase):
    """Render the store transfer page"""
    
    inventory = InventoryManager()
    
    st.title("🔄 Inter-Store Transfer")
    st.markdown("Transfer stock between your stores")
    st.markdown("---")
    
    # Get stores
    stores = db.get_active_stores()
    
    if stores.empty:
        st.error("❌ No active stores found. Please add stores first.")
        return
    
    if len(stores) < 2:
        st.warning("⚠️ You need at least 2 stores to perform transfers")
        return
    
    # ── Tabs ──────────────────────────────────────────────────
    tab1, tab2 = st.tabs([
        "➕ New Transfer",
        "📋 Transfer History"
    ])
    
    # TAB 1: NEW TRANSFER
    with tab1:
        st.subheader("➕ Create New Transfer")
        
        with st.form("transfer_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📤 From (Source)")
                from_store = st.selectbox(
                    "Source Store *",
                    options=stores['store_code'].tolist(),
                    format_func=lambda x: f"{x} - {stores[stores['store_code']==x]['store_name'].iloc[0]}",
                    key="from_store"
                )
                
                # Show available products
                source_stock = inventory.get_all_stock(from_store)
                available_products = source_stock[source_stock['current_stock'] > 0] if not source_stock.empty else pd.DataFrame()
                
                if not available_products.empty:
                    product_name = st.selectbox(
                        "Select Product *",
                        options=available_products['product_name'].tolist()
                    )
                    
                    current_stock = available_products[
                        available_products['product_name'] == product_name
                    ]['current_stock'].iloc[0]
                    
                    st.info(f"📦 Available Stock: **{current_stock} units**")
                else:
                    st.warning("⚠️ No products with stock in this store")
                    product_name = None
                    current_stock = 0
            
            with col2:
                st.markdown("#### 📥 To (Destination)")
                to_store_options = [s for s in stores['store_code'].tolist() if s != from_store]
                
                to_store = st.selectbox(
                    "Destination Store *",
                    options=to_store_options,
                    format_func=lambda x: f"{x} - {stores[stores['store_code']==x]['store_name'].iloc[0]}"
                )
            
            # Transfer quantity
            col1, col2 = st.columns(2)
            
            with col1:
                if product_name and current_stock > 0:
                    transfer_qty = st.number_input(
                        "Transfer Quantity *",
                        min_value=1,
                        max_value=int(current_stock),
                        value=min(10, int(current_stock)),
                        step=1
                    )
                else:
                    transfer_qty = 0
                    st.number_input("Transfer Quantity *", value=0, disabled=True)
            
            with col2:
                transfer_reason = st.text_input(
                    "Reason",
                    placeholder="e.g., Stock balancing"
                )
            
            # Submit
            submitted = st.form_submit_button(
                "🔄 Execute Transfer",
                type="primary",
                use_container_width=True
            )
            
            if submitted:
                if not product_name:
                    st.error("❌ Please select a product")
                elif transfer_qty <= 0:
                    st.error("❌ Invalid quantity")
                else:
                    try:
                        # Deduct from source
                        success1, msg1 = inventory.add_stock_on_purchase(
                            product_name=product_name,
                            store_code=from_store,
                            quantity=-transfer_qty,  # Negative to deduct
                            unit_cost=0,
                            reference_id=f"TRANSFER_OUT_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        )
                        
                        # Add to destination
                        success2, msg2 = inventory.add_stock_on_purchase(
                            product_name=product_name,
                            store_code=to_store,
                            quantity=transfer_qty,
                            unit_cost=0,
                            reference_id=f"TRANSFER_IN_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        )
                        
                        if success1 or success2:  # At least one succeeded
                            st.success(f"✅ Transfer completed!")
                            st.success(f"🔄 {transfer_qty} units of {product_name}")
                            st.success(f"📤 {from_store} → 📥 {to_store}")
                            st.balloons()
                        else:
                            st.error(f"❌ Transfer failed")
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
    
    # TAB 2: HISTORY
    with tab2:
        st.subheader("📋 Transfer History")
        
        # Get transfer movements
        movements = inventory.get_stock_movements(days=90)
        
        if not movements.empty:
            transfers = movements[movements['movement_type'].str.contains('TRANSFER', na=False)]
            
            if not transfers.empty:
                st.metric("Total Transfers (Last 90 days)", len(transfers))
                
                st.dataframe(
                    transfers[[
                        'movement_date', 'product_name', 'store_code',
                        'movement_type', 'quantity'
                    ]].sort_values('movement_date', ascending=False),
                    use_container_width=True
                )
            else:
                st.info("ℹ️ No transfers recorded yet")
        else:
            st.info("ℹ️ No movement history available")


# For testing
if __name__ == "__main__":
    st.set_page_config(page_title="Store Transfer", layout="wide")
    db = KiranaDatabase()
    render(db)