"""
app/stock_inward_page.py - Stock Inward Management
Easy UI for recording new stock arrivals and purchases
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict

from core.inventory_manager import InventoryManager
from core.database_manager import KiranaDatabase


def render(db: KiranaDatabase):
    """Render the stock inward page"""
    
    inventory = InventoryManager()
    
    st.title("📦 Stock Inward Management")
    st.markdown("Record new inventory arrivals and purchases")
    st.markdown("---")
    
    # ── Store Selection ──────────────────────────────────────
    stores = db.get_active_stores()
    
    if stores.empty:
        st.error("❌ No active stores found. Please add stores first.")
        if st.button("Go to Store Management"):
            st.session_state.page = 'Store Management'
            st.rerun()
        return
    
    # ── Tabs ──────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs([
        "➕ Add Single Item",
        "📋 Bulk Upload",
        "📜 Recent Receipts"
    ])
    
    # TAB 1: SINGLE ITEM ENTRY
    with tab1:
        st.subheader("➕ Add Stock - Single Item")
        
        with st.form("single_stock_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                store_code = st.selectbox(
                    "Store *",
                    options=stores['store_code'].tolist(),
                    format_func=lambda x: f"{x} - {stores[stores['store_code']==x]['store_name'].iloc[0]}"
                )
                
                product_name = st.text_input(
                    "Product Name *",
                    placeholder="e.g., Aashirvaad Atta 5kg"
                )
                
                quantity = st.number_input(
                    "Quantity Received *",
                    min_value=1,
                    value=50,
                    step=1
                )
                
                unit_cost = st.number_input(
                    "Unit Cost (₹) *",
                    min_value=0.01,
                    value=100.0,
                    step=0.01,
                    format="%.2f"
                )
            
            with col2:
                supplier_name = st.text_input(
                    "Supplier Name",
                    placeholder="e.g., ITC Limited"
                )
                
                invoice_number = st.text_input(
                    "Invoice/Bill Number",
                    placeholder="e.g., INV-2026-001"
                )
                
                received_date = st.date_input(
                    "Received Date",
                    value=datetime.now()
                )
                
                notes = st.text_area(
                    "Notes (Optional)",
                    placeholder="Any additional information..."
                )
            
            # Calculate total
            total_cost = quantity * unit_cost
            st.info(f"💰 **Total Cost:** ₹{total_cost:,.2f}")
            
            # Submit button
            submitted = st.form_submit_button(
                "✅ Add Stock",
                type="primary",
                use_container_width=True
            )
            
            if submitted:
                if not product_name:
                    st.error("❌ Product name is required!")
                elif quantity <= 0:
                    st.error("❌ Quantity must be greater than 0!")
                elif unit_cost <= 0:
                    st.error("❌ Unit cost must be greater than 0!")
                else:
                    # Add stock to inventory
                    success, message = inventory.add_stock_on_purchase(
                        product_name=product_name.strip(),
                        store_code=store_code,
                        quantity=quantity,
                        unit_cost=unit_cost,
                        reference_id=invoice_number if invoice_number else None
                    )
                    
                    if success:
                        st.success(f"✅ {message}")
                        st.success(f"📦 Added {quantity} units of {product_name}")
                        st.balloons()
                        
                        # Show updated stock
                        stock_info = inventory.get_current_stock(product_name, store_code)
                        if stock_info:
                            st.info(f"🔄 Updated Stock Level: **{stock_info['current_stock']} units**")
                    else:
                        st.error(f"❌ {message}")
    
    # TAB 2: BULK UPLOAD
    with tab2:
        st.subheader("📋 Bulk Stock Upload")
        st.write("Upload multiple items at once using CSV or Excel")
        
        # Download template
        st.markdown("### 1️⃣ Download Template")
        
        template_data = {
            'product_name': ['Aashirvaad Atta 5kg', 'Tata Salt 1kg', 'Fortune Oil 1L'],
            'quantity': [50, 100, 30],
            'unit_cost': [280.0, 20.0, 150.0],
            'supplier_name': ['ITC Limited', 'Tata Consumer', 'Adani Wilmar'],
            'invoice_number': ['INV-001', 'INV-002', 'INV-003']
        }
        template_df = pd.DataFrame(template_data)
        
        csv_template = template_df.to_csv(index=False)
        st.download_button(
            "📥 Download CSV Template",
            data=csv_template,
            file_name="stock_inward_template.csv",
            mime="text/csv"
        )
        
        st.markdown("### 2️⃣ Fill Template & Upload")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            uploaded_file = st.file_uploader(
                "Upload Stock Data",
                type=['csv', 'xlsx'],
                help="Upload filled template with your stock data"
            )
        
        with col2:
            bulk_store_code = st.selectbox(
                "Select Store for Bulk Upload",
                options=stores['store_code'].tolist(),
                format_func=lambda x: f"{x} - {stores[stores['store_code']==x]['store_name'].iloc[0]}",
                key="bulk_store"
            )
        
        if uploaded_file:
            try:
                # Read file
                if uploaded_file.name.endswith('.csv'):
                    upload_df = pd.read_csv(uploaded_file)
                else:
                    upload_df = pd.read_excel(uploaded_file)
                
                st.write("### 📊 Preview Data")
                st.dataframe(upload_df, use_container_width=True)
                
                # Validate columns
                required_cols = ['product_name', 'quantity', 'unit_cost']
                missing_cols = [col for col in required_cols if col not in upload_df.columns]
                
                if missing_cols:
                    st.error(f"❌ Missing required columns: {', '.join(missing_cols)}")
                else:
                    total_items = len(upload_df)
                    total_cost = (upload_df['quantity'] * upload_df['unit_cost']).sum()
                    
                    col1, col2 = st.columns(2)
                    col1.metric("Total Items", total_items)
                    col2.metric("Total Cost", f"₹{total_cost:,.2f}")
                    
                    if st.button("✅ Process Bulk Upload", type="primary"):
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        success_count = 0
                        failed_items = []
                        
                        for idx, row in upload_df.iterrows():
                            progress = (idx + 1) / total_items
                            progress_bar.progress(progress)
                            status_text.text(f"Processing {idx + 1}/{total_items}: {row['product_name']}")
                            
                            success, message = inventory.add_stock_on_purchase(
                                product_name=row['product_name'],
                                store_code=bulk_store_code,
                                quantity=int(row['quantity']),
                                unit_cost=float(row['unit_cost']),
                                reference_id=row.get('invoice_number', None)
                            )
                            
                            if success:
                                success_count += 1
                            else:
                                failed_items.append(row['product_name'])
                        
                        progress_bar.empty()
                        status_text.empty()
                        
                        if success_count == total_items:
                            st.success(f"🎉 Successfully added {success_count} items!")
                            st.balloons()
                        else:
                            st.warning(f"⚠️ Added {success_count}/{total_items} items")
                            if failed_items:
                                st.error(f"Failed items: {', '.join(failed_items)}")
                
            except Exception as e:
                st.error(f"❌ Error reading file: {e}")
    
    # TAB 3: RECENT RECEIPTS
    with tab3:
        st.subheader("📜 Recent Stock Receipts")
        
        # Filters
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filter_store = st.selectbox(
                "Filter by Store",
                options=['All Stores'] + stores['store_code'].tolist(),
                key="recent_store"
            )
        
        with col2:
            days_filter = st.selectbox(
                "Time Period",
                options=[7, 15, 30, 60, 90],
                format_func=lambda x: f"Last {x} days",
                index=2
            )
        
        with col3:
            movement_type_filter = st.selectbox(
                "Type",
                options=['All', 'Purchase Only'],
                key="movement_filter"
            )
        
        # Get movements
        store_filter = None if filter_store == 'All Stores' else filter_store
        movements = inventory.get_stock_movements(
            product_name=None,
            store_code=store_filter,
            days=days_filter
        )
        
        if not movements.empty:
            # Filter by type
            if movement_type_filter == 'Purchase Only':
                movements = movements[movements['movement_type'] == 'PURCHASE']
            else:
                movements = movements[movements['movement_type'].isin(['PURCHASE', 'ADJUSTMENT'])]
            
            if not movements.empty:
                movements['movement_date'] = pd.to_datetime(movements['movement_date'])
                
                # Summary metrics
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Receipts", len(movements))
                col2.metric("Items Received", int(movements['quantity'].sum()))
                col3.metric("Total Value", f"₹{movements['total_value'].sum():,.2f}")
                
                unique_products = movements['product_name'].nunique()
                col4.metric("Unique Products", unique_products)
                
                st.markdown("---")
                
                # Detailed table
                display_df = movements[[
                    'movement_date', 'product_name', 'store_code',
                    'quantity', 'unit_cost', 'total_value', 'reference_id'
                ]].sort_values('movement_date', ascending=False)
                
                st.dataframe(
                    display_df.style.format({
                        'unit_cost': '₹{:.2f}',
                        'total_value': '₹{:,.2f}',
                        'movement_date': lambda x: x.strftime('%Y-%m-%d %H:%M')
                    }),
                    use_container_width=True,
                    height=400
                )
                
                # Export
                csv_data = display_df.to_csv(index=False)
                st.download_button(
                    "📥 Export to CSV",
                    data=csv_data,
                    file_name=f"stock_receipts_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("ℹ️ No purchase receipts found for selected filters")
        else:
            st.info("ℹ️ No stock movements recorded yet")


# For standalone testing
if __name__ == "__main__":
    st.set_page_config(page_title="Stock Inward", layout="wide")
    db = KiranaDatabase()
    render(db)