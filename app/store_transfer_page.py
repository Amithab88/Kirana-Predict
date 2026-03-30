"""
app/store_transfer_page.py — Inter-Store Transfer Management
=============================================================
Transfer stock between stores with proper TRANSFER_OUT / TRANSFER_IN
movement types and full audit trail.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from core.database_manager import KiranaDatabase
from core.inventory_manager import InventoryManager


def render(db: KiranaDatabase):
    """Render the store transfer page."""

    inventory = InventoryManager()

    st.title("🔄 Inter-Store Transfer")
    st.markdown("Transfer stock between your stores")
    st.markdown("---")

    # ── Store validation ──────────────────────────────────────────
    stores = db.get_active_stores()

    if stores.empty:
        st.error("❌ No active stores found. Please add stores first.")
        return

    if len(stores) < 2:
        st.warning("⚠️ You need at least 2 active stores to perform transfers.")
        return

    # ── Tabs ──────────────────────────────────────────────────────
    tab1, tab2 = st.tabs(["➕ New Transfer", "📋 Transfer History"])

    # ══════════════════════════════════════════════════════════════
    # TAB 1: NEW TRANSFER
    # ══════════════════════════════════════════════════════════════
    with tab1:
        st.subheader("➕ Create New Transfer")

        with st.form("transfer_form", clear_on_submit=True):
            col_src, col_dst = st.columns(2)

            # ── Source store ──────────────────────────────────────
            with col_src:
                st.markdown("#### 📤 From (Source)")
                from_store = st.selectbox(
                    "Source Store *",
                    options=stores['store_code'].tolist(),
                    format_func=lambda x: (
                        f"{x} — {stores[stores['store_code']==x]['store_name'].iloc[0]}"
                    ),
                    key="from_store",
                )

            # ── Destination store ─────────────────────────────────
            with col_dst:
                st.markdown("#### 📥 To (Destination)")
                to_store_options = [
                    s for s in stores['store_code'].tolist() if s != from_store
                ]
                to_store = st.selectbox(
                    "Destination Store *",
                    options=to_store_options,
                    format_func=lambda x: (
                        f"{x} — {stores[stores['store_code']==x]['store_name'].iloc[0]}"
                    ),
                    key="to_store",
                )

            st.markdown("---")

            # ── Product & quantity ────────────────────────────────
            source_stock = inventory.get_all_stock(from_store)
            available = (
                source_stock[source_stock['current_stock'] > 0]
                if not source_stock.empty else pd.DataFrame()
            )

            pcol, qcol = st.columns(2)

            product_name = None
            current_stock = 0
            transfer_qty = 0

            with pcol:
                if not available.empty:
                    product_name = st.selectbox(
                        "Select Product *",
                        options=available['product_name'].tolist(),
                    )
                    current_stock = int(
                        available[available['product_name'] == product_name]
                        ['current_stock'].iloc[0]
                    )
                    st.info(f"📦 Available: **{current_stock} units**")
                else:
                    st.warning("⚠️ No products with stock at source store")
                    st.text_input("Product", disabled=True, value="—")

            with qcol:
                if product_name and current_stock > 0:
                    transfer_qty = st.number_input(
                        "Transfer Quantity *",
                        min_value=1,
                        max_value=current_stock,
                        value=min(10, current_stock),
                        step=1,
                    )
                else:
                    st.number_input("Transfer Quantity *", value=0, disabled=True)

            transfer_reason = st.text_input(
                "Reason (optional)",
                placeholder="e.g., Stock balancing, demand spike at destination",
            )

            # ── Preview ──────────────────────────────────────────
            if product_name and transfer_qty > 0:
                # Show what destination currently has
                dst_stock = inventory.get_current_stock(product_name, to_store)
                dst_current = dst_stock['current_stock'] if dst_stock else 0

                pcol1, pcol2, pcol3 = st.columns(3)
                pcol1.metric(
                    f"📤 {from_store} After",
                    f"{current_stock - transfer_qty} units",
                    delta=f"-{transfer_qty}",
                    delta_color="inverse",
                )
                pcol2.metric("🔄 Transferring", f"{transfer_qty} units")
                pcol3.metric(
                    f"📥 {to_store} After",
                    f"{dst_current + transfer_qty} units",
                    delta=f"+{transfer_qty}",
                )

            # ── Submit ───────────────────────────────────────────
            submitted = st.form_submit_button(
                "🔄 Execute Transfer",
                type="primary",
                use_container_width=True,
            )

            if submitted:
                if not product_name:
                    st.error("❌ Please select a product")
                elif transfer_qty <= 0:
                    st.error("❌ Quantity must be greater than 0")
                elif from_store == to_store:
                    st.error("❌ Source and destination must differ")
                else:
                    with st.spinner("Processing transfer…"):
                        success, msg = inventory.transfer_stock(
                            product_name=product_name,
                            from_store=from_store,
                            to_store=to_store,
                            quantity=transfer_qty,
                            reason=transfer_reason,
                        )

                    if success:
                        st.success(msg)
                        st.balloons()
                    else:
                        st.error(msg)

    # ══════════════════════════════════════════════════════════════
    # TAB 2: TRANSFER HISTORY
    # ══════════════════════════════════════════════════════════════
    with tab2:
        st.subheader("📋 Transfer History")

        hcol1, hcol2 = st.columns(2)
        with hcol1:
            history_days = st.selectbox(
                "Time Period",
                options=[7, 15, 30, 60, 90],
                format_func=lambda x: f"Last {x} days",
                index=2,
            )
        with hcol2:
            history_store = st.selectbox(
                "Filter by Store",
                options=['All Stores'] + stores['store_code'].tolist(),
                key="history_store",
            )

        hist_store = None if history_store == 'All Stores' else history_store

        movements = inventory.get_stock_movements(
            store_code=hist_store, days=history_days
        )

        if not movements.empty:
            transfers = movements[
                movements['movement_type'].str.contains('TRANSFER', na=False)
            ]

            if not transfers.empty:
                # Summary
                tcol1, tcol2, tcol3 = st.columns(3)
                tcol1.metric("Total Transfer Movements", len(transfers))
                tcol2.metric("Transfer Out",
                             len(transfers[transfers['movement_type'] == 'TRANSFER_OUT']))
                tcol3.metric("Transfer In",
                             len(transfers[transfers['movement_type'] == 'TRANSFER_IN']))

                st.markdown("---")

                # Table
                display_cols = ['movement_date', 'product_name', 'store_code',
                                'movement_type', 'quantity']
                for c in ['reference_id', 'notes']:
                    if c in transfers.columns:
                        display_cols.append(c)

                st.dataframe(
                    transfers[display_cols].sort_values('movement_date', ascending=False),
                    use_container_width=True,
                    height=400,
                )

                # Export
                csv_data = transfers[display_cols].to_csv(index=False)
                st.download_button(
                    "📥 Export Transfers (CSV)",
                    data=csv_data,
                    file_name=f"transfers_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                )

                # Trend chart
                if len(transfers) > 1:
                    st.write("**Transfer Volume Over Time**")
                    transfers_copy = transfers.copy()
                    transfers_copy['date'] = transfers_copy['movement_date'].dt.date
                    daily_t = transfers_copy.groupby(['date', 'movement_type']).agg(
                        qty=('quantity', 'sum'),
                    ).reset_index()

                    fig = px.bar(
                        daily_t, x='date', y='qty', color='movement_type',
                        barmode='group',
                        labels={'qty': 'Units', 'date': 'Date'},
                        color_discrete_map={
                            'TRANSFER_OUT': '#f44336',
                            'TRANSFER_IN': '#4caf50',
                        },
                    )
                    fig.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                    )
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("ℹ️ No transfers recorded in the selected period.")
        else:
            st.info("ℹ️ No movement history available.")


# For standalone testing
if __name__ == "__main__":
    st.set_page_config(page_title="Store Transfer", layout="wide")
    db = KiranaDatabase()
    render(db)