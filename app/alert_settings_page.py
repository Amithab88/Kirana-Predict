"""
app/alert_settings_page.py – Email Alert Configuration and Testing page.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from core.email_manager import EmailAlertManager


def render(df: pd.DataFrame):
    st.title("📧 Email Alert Settings")
    st.markdown("### Configure automated notifications and reports")

    email_manager = EmailAlertManager()

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

    # Config display
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

            test_product = st.selectbox("Select Product", df['product_name'].unique().tolist(), key="test_product_alert")
            test_stock = st.number_input("Current Stock", min_value=0, value=10, key="test_stock")
            test_daily_sales = st.number_input("Avg Daily Sales", min_value=0.1, value=5.0, step=0.1, key="test_daily")

            if st.button("📧 Send Test Low Stock Alert", use_container_width=True):
                days_remaining = test_stock / test_daily_sales if test_daily_sales > 0 else 0
                html = email_manager.create_low_stock_alert(
                    product_name=test_product, current_stock=test_stock,
                    days_remaining=days_remaining, avg_daily_sales=test_daily_sales
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

            summary_date = st.date_input("Summary Date", value=datetime.now().date(), key="summary_date")
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

        # Stock Alert Check
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
                                'product_name': product, 'current_stock': current_stock,
                                'days_remaining': days_remaining, 'avg_daily_sales': avg_daily
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
        """)
