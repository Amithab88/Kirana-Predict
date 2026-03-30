"""
app/notifications_page.py — Notification Center
=================================================
Unified notification hub with:
  • In-app notification feed (from Supabase `notifications` table)
  • Email alerts (low-stock + daily summary via EmailAlertManager)
  • WhatsApp alerts via Twilio API
  • Notification preferences / settings

Accessible to Admin users only.
"""

import os
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional

from core.database_manager import KiranaDatabase
from core.inventory_manager import InventoryManager
from core.email_manager import EmailAlertManager

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ────────────────────────────────────────────────────────────────────
# WHATSAPP SENDER (Twilio)
# ────────────────────────────────────────────────────────────────────

class WhatsAppSender:
    """Send WhatsApp messages via Twilio API."""

    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID', '')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN', '')
        self.from_number = os.getenv('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
        self.enabled = bool(self.account_sid and self.auth_token)

    def send_message(self, to_number: str, message: str) -> bool:
        """
        Send a WhatsApp message.
        to_number: e.g. '+919876543210' (will be prefixed with whatsapp:)
        """
        if not self.enabled:
            print("⚠️ WhatsApp not configured (TWILIO_ACCOUNT_SID / AUTH_TOKEN missing)")
            return False

        try:
            from twilio.rest import Client
            client = Client(self.account_sid, self.auth_token)

            to_wa = f"whatsapp:{to_number}" if not to_number.startswith('whatsapp:') else to_number

            client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_wa,
            )
            print(f"✅ WhatsApp sent to {to_number}")
            return True

        except ImportError:
            print("❌ twilio package not installed. Run: pip install twilio")
            return False
        except Exception as e:
            print(f"❌ WhatsApp error: {e}")
            return False

    def send_low_stock_alert(self, to_number: str,
                              product_name: str,
                              current_stock: int,
                              days_left: float,
                              store_code: str) -> bool:
        """Pre-formatted low-stock WhatsApp alert."""
        urgency = "🚨 CRITICAL" if days_left < 3 else "⚠️ LOW STOCK"

        msg = (
            f"{urgency} — {product_name}\n\n"
            f"📍 Store: {store_code}\n"
            f"📦 Stock: {current_stock} units\n"
            f"⏰ Days left: {days_left:.1f}\n\n"
            f"Action: Place a purchase order\n"
            f"— Kirana-Predict Pro"
        )
        return self.send_message(to_number, msg)

    def send_daily_summary(self, to_number: str,
                            health_score: dict,
                            low_stock_count: int) -> bool:
        """Pre-formatted daily summary WhatsApp."""
        msg = (
            f"📊 Daily Inventory Summary\n"
            f"{'='*28}\n\n"
            f"Health: {health_score['score']}/100 (Grade {health_score['grade']})\n"
            f"Products: {health_score['total_products']}\n"
            f"In Stock: {health_score['in_stock']}\n"
            f"Critical: {health_score['critical_items']}\n"
            f"Need Reorder: {low_stock_count}\n\n"
            f"Check dashboard for details.\n"
            f"— Kirana-Predict Pro"
        )
        return self.send_message(to_number, msg)


# ────────────────────────────────────────────────────────────────────
# RENDER
# ────────────────────────────────────────────────────────────────────

def render(db: KiranaDatabase):
    """Render the notifications page."""

    inventory = InventoryManager()
    email_mgr = EmailAlertManager()
    wa_sender = WhatsAppSender()

    st.title("🔔 Notification Center")
    st.markdown("Manage alerts across Email, WhatsApp, and in-app notifications")
    st.markdown("---")

    # ── Tabs ──────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📥 Notifications",
        "📧 Email Alerts",
        "💬 WhatsApp Alerts",
        "⚙️ Settings",
    ])

    # ══════════════════════════════════════════════════════════════
    # TAB 1: IN-APP NOTIFICATIONS
    # ══════════════════════════════════════════════════════════════
    with tab1:
        st.subheader("📥 Recent Notifications")

        hcol1, hcol2, hcol3 = st.columns([2, 1, 1])
        with hcol1:
            show_unread = st.checkbox("Show unread only", value=False)
        with hcol2:
            unread_count = db.get_unread_count()
            st.metric("Unread", unread_count)
        with hcol3:
            if st.button("✅ Mark All Read"):
                db.mark_all_notifications_read()
                st.success("All notifications marked as read")
                st.rerun()

        st.markdown("---")

        notifications = db.get_notifications(limit=50, unread_only=show_unread)

        if not notifications.empty:
            for _, notif in notifications.iterrows():
                severity_icon = {
                    'critical': '🚨',
                    'warning': '⚠️',
                    'info': 'ℹ️',
                }.get(notif.get('severity', 'info'), 'ℹ️')

                type_badge = {
                    'low_stock': '📦',
                    'forecast': '🔮',
                    'transfer': '🔄',
                    'system': '🔧',
                }.get(notif.get('type', 'system'), '📋')

                is_read = notif.get('is_read', True)
                read_marker = "🔵 " if not is_read else ""

                created = ""
                if pd.notna(notif.get('created_at')):
                    created = pd.to_datetime(notif['created_at']).strftime('%d %b %Y, %H:%M')

                with st.expander(
                    f"{read_marker}{severity_icon} {type_badge} "
                    f"{notif.get('title', 'Notification')}  —  {created}",
                    expanded=not is_read,
                ):
                    st.write(notif.get('message', ''))

                    if notif.get('store_code'):
                        st.caption(f"Store: {notif['store_code']}")

                    if not is_read:
                        if st.button("Mark as read", key=f"read_{notif.get('id', _)}"):
                            db.mark_notification_read(notif['id'])
                            st.rerun()
        else:
            st.info("🎉 No notifications to show — you're all caught up!")

        # ── Generate alerts button ────────────────────────────────
        st.markdown("---")
        if st.button("🔄 Scan & Generate Low-Stock Alerts", type="primary"):
            with st.spinner("Scanning inventory…"):
                suggestions = inventory.generate_reorder_suggestions(priority='soon')
                created = 0

                for _, item in suggestions.iterrows():
                    severity = 'critical' if item['priority'] == 'URGENT' else 'warning'
                    db.insert_notification({
                        'title': f"{item['priority']}: {item['product_name']}",
                        'message': (
                            f"Stock: {item['current_stock']} units | "
                            f"Daily usage: {item['daily_consumption']:.1f} | "
                            f"Days left: {item['days_until_stockout']} | "
                            f"{item['reasoning']}"
                        ),
                        'type': 'low_stock',
                        'severity': severity,
                        'store_code': item['store_code'],
                    })
                    created += 1

                if created > 0:
                    st.success(f"✅ Created {created} new low-stock notifications")
                    st.rerun()
                else:
                    st.success("✅ All inventory levels are healthy — no alerts needed!")

    # ══════════════════════════════════════════════════════════════
    # TAB 2: EMAIL ALERTS
    # ══════════════════════════════════════════════════════════════
    with tab2:
        st.subheader("📧 Email Alerts")

        # Status
        if email_mgr.enabled:
            st.success(f"✅ Email alerts are **enabled** ({email_mgr.service.upper()})")
            st.caption(f"Sender: {email_mgr.sender}")
        else:
            st.warning(
                "⚠️ Email alerts are **disabled**. "
                "Set EMAIL_ENABLED=true in your .env or Streamlit secrets."
            )

        st.markdown("---")

        # ── Send low-stock alert email ────────────────────────────
        st.write("**📦 Low-Stock Alert Email**")

        stores = db.get_active_stores()
        store_list = stores['store_code'].tolist() if not stores.empty else []

        ecol1, ecol2 = st.columns(2)
        with ecol1:
            alert_store = st.selectbox(
                "Store", store_list, key="email_alert_store"
            )
        with ecol2:
            email_recipients = st.text_area(
                "Recipients (one per line)",
                value=os.getenv('EMAIL_RECIPIENTS', ''),
                height=100,
            )

        if st.button("📧 Send Low-Stock Alert", type="primary"):
            recipients = [r.strip() for r in email_recipients.split('\n') if r.strip()]
            if not recipients:
                st.error("❌ Please enter at least one recipient")
            else:
                with st.spinner("Generating alert…"):
                    suggestions = inventory.generate_reorder_suggestions(
                        store_code=alert_store, priority='soon'
                    )

                    if suggestions.empty:
                        st.info("✅ No low-stock items — nothing to alert about.")
                    else:
                        # Build email body
                        items_html = ""
                        for _, item in suggestions.iterrows():
                            color = '#f44336' if item['priority'] == 'URGENT' else '#ff9800'
                            items_html += f"""
                            <tr>
                                <td style="color:{color};font-weight:bold">{item['priority']}</td>
                                <td>{item['product_name']}</td>
                                <td>{item['current_stock']}</td>
                                <td>{item['daily_consumption']:.1f}</td>
                                <td>{item['days_until_stockout']} days</td>
                                <td>{item['suggested_order_qty']}</td>
                                <td>₹{item['order_cost_estimate']:,.2f}</td>
                            </tr>"""

                        html_body = f"""
                        <html><body style="font-family:Arial,sans-serif">
                        <div style="background:#f44336;color:white;padding:20px;border-radius:8px 8px 0 0">
                            <h1>🚨 Low Stock Alert — {alert_store}</h1>
                            <p>{datetime.now().strftime('%d %b %Y, %H:%M')}</p>
                        </div>
                        <div style="padding:20px;background:#fafafa;border:1px solid #ddd">
                            <p><strong>{len(suggestions)}</strong> products need reordering.</p>
                            <table style="width:100%;border-collapse:collapse;margin:15px 0">
                                <tr style="background:#333;color:white">
                                    <th style="padding:10px">Priority</th>
                                    <th style="padding:10px">Product</th>
                                    <th style="padding:10px">Stock</th>
                                    <th style="padding:10px">Daily Use</th>
                                    <th style="padding:10px">Days Left</th>
                                    <th style="padding:10px">Order Qty</th>
                                    <th style="padding:10px">Est. Cost</th>
                                </tr>
                                {items_html}
                            </table>
                            <p style="color:#666;font-size:12px">
                                Automated alert from Kirana-Predict Pro
                            </p>
                        </div>
                        </body></html>"""

                        subject = (
                            f"🚨 Low Stock Alert — {alert_store} — "
                            f"{len(suggestions)} items need reordering"
                        )
                        success = email_mgr.send_email(
                            subject=subject,
                            html_body=html_body,
                            recipients=recipients,
                        )
                        if success:
                            st.success(f"✅ Alert sent to {len(recipients)} recipient(s)")
                        else:
                            st.error("❌ Failed to send email. Check configuration.")

        st.markdown("---")

        # ── Send daily summary email ──────────────────────────────
        st.write("**📊 Daily Summary Email**")
        if st.button("📧 Send Daily Summary"):
            recipients = [r.strip() for r in email_recipients.split('\n') if r.strip()]
            if not recipients:
                st.error("❌ Please enter recipients above")
            else:
                with st.spinner("Generating summary…"):
                    sales = db.get_recent_sales(days=1)
                    if not sales.empty:
                        html = email_mgr.create_daily_summary(sales)
                        subject = f"📊 Daily Summary — {datetime.now().strftime('%d %b %Y')}"
                        success = email_mgr.send_email(subject=subject, html_body=html,
                                                        recipients=recipients)
                        if success:
                            st.success("✅ Daily summary sent!")
                        else:
                            st.error("❌ Failed to send summary.")
                    else:
                        st.info("No sales today — nothing to summarize.")

    # ══════════════════════════════════════════════════════════════
    # TAB 3: WHATSAPP ALERTS
    # ══════════════════════════════════════════════════════════════
    with tab3:
        st.subheader("💬 WhatsApp Alerts")

        if wa_sender.enabled:
            st.success("✅ WhatsApp (Twilio) is **configured**")
        else:
            st.warning(
                "⚠️ WhatsApp is **not configured**. "
                "Add TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and "
                "TWILIO_WHATSAPP_FROM to your .env file."
            )
            st.markdown("""
            **Setup Instructions:**
            1. Create a [Twilio account](https://www.twilio.com/try-twilio)
            2. Activate the WhatsApp Sandbox in Twilio Console
            3. Add these to your `.env`:
            ```
            TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
            TWILIO_AUTH_TOKEN=your_auth_token_here
            TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
            ```
            """)

        st.markdown("---")

        wa_col1, wa_col2 = st.columns(2)

        with wa_col1:
            wa_phone = st.text_input(
                "Recipient WhatsApp Number",
                placeholder="+919876543210",
                help="Include country code with + prefix",
            )

        with wa_col2:
            wa_store = st.selectbox(
                "Store",
                store_list if store_list else ['—'],
                key="wa_store",
            )

        # ── Send test message ─────────────────────────────────────
        st.write("**🧪 Test Message**")
        if st.button("📲 Send Test WhatsApp"):
            if not wa_phone:
                st.error("❌ Enter a phone number")
            elif not wa_sender.enabled:
                st.error("❌ WhatsApp not configured")
            else:
                test_msg = (
                    "✅ Kirana-Predict Pro\n\n"
                    "This is a test message from your inventory dashboard.\n"
                    f"Time: {datetime.now().strftime('%d %b %Y, %H:%M')}"
                )
                success = wa_sender.send_message(wa_phone, test_msg)
                if success:
                    st.success("✅ Test message sent!")
                else:
                    st.error("❌ Failed to send. Check Twilio configuration.")

        st.markdown("---")

        # ── Send low-stock WhatsApp ───────────────────────────────
        st.write("**📦 Low-Stock WhatsApp Alert**")
        if st.button("📲 Send Low-Stock via WhatsApp", type="primary"):
            if not wa_phone:
                st.error("❌ Enter a phone number")
            elif not wa_sender.enabled:
                st.error("❌ WhatsApp not configured")
            else:
                with st.spinner("Scanning & sending…"):
                    suggestions = inventory.generate_reorder_suggestions(
                        store_code=wa_store, priority='soon'
                    )
                    sent = 0
                    if not suggestions.empty:
                        for _, item in suggestions.head(5).iterrows():
                            ok = wa_sender.send_low_stock_alert(
                                to_number=wa_phone,
                                product_name=item['product_name'],
                                current_stock=item['current_stock'],
                                days_left=item['days_until_stockout'],
                                store_code=item['store_code'],
                            )
                            if ok:
                                sent += 1
                        st.success(f"✅ Sent {sent} WhatsApp alert(s)")
                    else:
                        st.success("✅ All stock levels healthy — no alerts needed!")

        st.markdown("---")

        # ── Send daily summary WhatsApp ───────────────────────────
        st.write("**📊 Daily Summary via WhatsApp**")
        if st.button("📲 Send Daily Summary"):
            if not wa_phone:
                st.error("❌ Enter a phone number")
            elif not wa_sender.enabled:
                st.error("❌ WhatsApp not configured")
            else:
                health = inventory.get_inventory_health_score(wa_store)
                low_count = len(inventory.get_low_stock_items(wa_store))
                success = wa_sender.send_daily_summary(wa_phone, health, low_count)
                if success:
                    st.success("✅ Daily summary sent via WhatsApp!")
                else:
                    st.error("❌ Failed to send.")

    # ══════════════════════════════════════════════════════════════
    # TAB 4: SETTINGS
    # ══════════════════════════════════════════════════════════════
    with tab4:
        st.subheader("⚙️ Notification Preferences")

        st.write("**Alert Thresholds**")
        scol1, scol2 = st.columns(2)
        with scol1:
            urgent_days = st.number_input(
                "Urgent alert (days until stockout)",
                min_value=1, max_value=7, value=3,
            )
        with scol2:
            warning_days = st.number_input(
                "Warning alert (days until stockout)",
                min_value=3, max_value=14, value=7,
            )

        st.markdown("---")

        st.write("**Channel Configuration Status**")

        config_data = {
            'Channel': ['📧 Email (SMTP)', '📧 Email (SendGrid)', '💬 WhatsApp (Twilio)'],
            'Status': [
                '✅ Configured' if email_mgr.enabled and email_mgr.service == 'gmail' else '❌ Not configured',
                '✅ Configured' if email_mgr.enabled and email_mgr.service == 'sendgrid' else '❌ Not configured',
                '✅ Configured' if wa_sender.enabled else '❌ Not configured',
            ],
            'Details': [
                f"Server: {getattr(email_mgr, 'smtp_server', 'N/A')}" if email_mgr.enabled else "Set EMAIL_ENABLED=true",
                f"API key: {'****' + getattr(email_mgr, 'api_key', '')[-4:]}" if hasattr(email_mgr, 'api_key') and email_mgr.api_key else "Set SENDGRID_API_KEY",
                f"From: {wa_sender.from_number}" if wa_sender.enabled else "Set TWILIO_ACCOUNT_SID",
            ],
        }
        st.dataframe(pd.DataFrame(config_data), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.write("**Required Environment Variables**")
        st.code("""
# Email (Gmail SMTP)
EMAIL_ENABLED=true
EMAIL_SERVICE=gmail
EMAIL_SENDER=your@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_RECIPIENTS=admin@store.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Email (SendGrid) — alternative
# EMAIL_SERVICE=sendgrid
# SENDGRID_API_KEY=SG.xxxxx

# WhatsApp (Twilio)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
        """, language="bash")


# For standalone testing
if __name__ == "__main__":
    st.set_page_config(page_title="Notifications", layout="wide")
    db = KiranaDatabase()
    render(db)
