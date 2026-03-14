import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import pandas as pd
from typing import List, Dict, Optional

try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False

from dotenv import load_dotenv

load_dotenv()


class EmailAlertManager:
    """Manages email alerts for inventory and sales"""

    def __init__(self):
        """Initialize email configuration"""
        self.load_config()

    def load_config(self):
        """Load email configuration from environment or Streamlit secrets"""
        if STREAMLIT_AVAILABLE and hasattr(st, "secrets"):
            try:
                self.enabled = (
                    st.secrets.get("EMAIL_ENABLED", "false").lower() == "true"
                )
                self.service = st.secrets.get("EMAIL_SERVICE", "gmail")
                self.sender = st.secrets.get("EMAIL_SENDER", "")
                self.recipients = st.secrets.get("EMAIL_RECIPIENTS", "").split(",")

                if self.service == "gmail":
                    self.smtp_server = st.secrets.get(
                        "SMTP_SERVER", "smtp.gmail.com"
                    )
                    self.smtp_port = int(st.secrets.get("SMTP_PORT", "587"))
                    self.password = st.secrets.get("EMAIL_PASSWORD", "")
                elif self.service == "sendgrid":
                    self.api_key = st.secrets.get("SENDGRID_API_KEY", "")
            except Exception:
                self._load_from_env()
        else:
            self._load_from_env()

    def _load_from_env(self):
        """Fallback to environment variables"""
        self.enabled = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
        self.service = os.getenv("EMAIL_SERVICE", "gmail")
        self.sender = os.getenv("EMAIL_SENDER", "")
        self.recipients = os.getenv("EMAIL_RECIPIENTS", "").split(",")

        if self.service == "gmail":
            self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
            self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
            self.password = os.getenv("EMAIL_PASSWORD", "")
        elif self.service == "sendgrid":
            self.api_key = os.getenv("SENDGRID_API_KEY", "")

    def send_email(
        self, subject: str, html_body: str, recipients: Optional[List[str]] = None
    ) -> bool:
        """Send email using configured service"""
        if not self.enabled:
            print("⚠️ Email alerts are disabled")
            return False

        if not recipients:
            recipients = [r.strip() for r in self.recipients if r.strip()]

        if not recipients:
            print("❌ No recipients configured")
            return False

        try:
            if self.service == "gmail":
                return self._send_via_gmail(subject, html_body, recipients)
            elif self.service == "sendgrid":
                return self._send_via_sendgrid(subject, html_body, recipients)
            else:
                print(f"❌ Unknown email service: {self.service}")
                return False
        except Exception as e:
            print(f"❌ Email send failed: {e}")
            return False

    def _send_via_gmail(
        self, subject: str, html_body: str, recipients: List[str]
    ) -> bool:
        """Send email via Gmail SMTP"""
        msg = MIMEMultipart("alternative")
        msg["From"] = self.sender
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject

        html_part = MIMEText(html_body, "html")
        msg.attach(html_part)

        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.sender, self.password)
            server.send_message(msg)

        print(f"✅ Email sent to {len(recipients)} recipient(s)")
        return True

    def _send_via_sendgrid(
        self, subject: str, html_body: str, recipients: List[str]
    ) -> bool:
        """Send email via SendGrid API"""
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail
        except ImportError:
            print("❌ SendGrid library not installed. Run: pip install sendgrid")
            return False

        message = Mail(
            from_email=self.sender,
            to_emails=recipients,
            subject=subject,
            html_content=html_body,
        )

        sg = SendGridAPIClient(self.api_key)
        response = sg.send(message)

        print(f"✅ Email sent via SendGrid (status: {response.status_code})")
        return True

    def create_low_stock_alert(
        self,
        product_name: str,
        current_stock: int,
        days_remaining: float,
        avg_daily_sales: float,
    ) -> str:
        """Generate HTML for low stock alert"""

        if days_remaining < 3:
            urgency = "CRITICAL"
            color = "#d32f2f"
            icon = "🚨"
        elif days_remaining < 7:
            urgency = "WARNING"
            color = "#f57c00"
            icon = "⚠️"
        else:
            urgency = "NOTICE"
            color = "#1976d2"
            icon = "ℹ️"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: {color}; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
                .alert-box {{ background-color: white; padding: 15px; margin: 15px 0; border-left: 4px solid {color}; }}
                .metrics {{ display: flex; justify-content: space-around; margin: 20px 0; }}
                .metric {{ text-align: center; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: {color}; }}
                .metric-label {{ font-size: 12px; color: #666; }}
                .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
                .button {{ background-color: {color}; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{icon} {urgency} STOCK ALERT</h1>
                </div>
                <div class="content">
                    <div class="alert-box">
                        <h2>Low Stock Warning: {product_name}</h2>
                        <p>Immediate attention required for inventory replenishment.</p>
                    </div>
                    
                    <div class="metrics">
                        <div class="metric">
                            <div class="metric-value">{current_stock}</div>
                            <div class="metric-label">Current Stock</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">{days_remaining:.1f}</div>
                            <div class="metric-label">Days Remaining</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">{avg_daily_sales:.1f}</div>
                            <div class="metric-label">Avg Daily Sales</div>
                        </div>
                    </div>
                    
                    <div class="alert-box">
                        <h3>📋 Recommended Actions:</h3>
                        <ul>
                            <li>Order minimum {int(avg_daily_sales * 14)} units for 2-week supply</li>
                            <li>Expected stockout: {(datetime.now() + timedelta(days=days_remaining)).strftime('%d %b %Y')}</li>
                            <li>Review recent sales trends for unusual patterns</li>
                        </ul>
                    </div>
                    
                    <p style="text-align: center;">
                        <a href="https://kirana-predict.streamlit.app/" class="button">
                            View Full Dashboard
                        </a>
                    </p>
                </div>
                <div class="footer">
                    <p>Kirana-Predict Alert System | {datetime.now().strftime('%d %b %Y, %I:%M %p')}</p>
                    <p>This is an automated alert. Do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def create_daily_summary(self, sales_df: pd.DataFrame) -> str:
        """Generate HTML for daily sales summary"""

        today = datetime.now().strftime("%d %b %Y")
        total_revenue = sales_df["total_amount"].sum()
        total_transactions = len(sales_df)
        total_units = sales_df["quantity"].sum()

        top_products = (
            sales_df.groupby("product_name")["total_amount"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )

        top_products_html = ""
        for i, (product, revenue) in enumerate(top_products.items(), 1):
            top_products_html += f"<li><strong>{product}</strong>: ₹{revenue:,.2f}</li>"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #1976d2; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
                .metrics {{ display: flex; justify-content: space-around; margin: 20px 0; background: white; padding: 15px; border-radius: 5px; }}
                .metric {{ text-align: center; }}
                .metric-value {{ font-size: 28px; font-weight: bold; color: #1976d2; }}
                .metric-label {{ font-size: 12px; color: #666; margin-top: 5px; }}
                .section {{ background: white; padding: 15px; margin: 15px 0; border-radius: 5px; }}
                .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 Daily Sales Summary</h1>
                    <p>{today}</p>
                </div>
                <div class="content">
                    <div class="metrics">
                        <div class="metric">
                            <div class="metric-value">₹{total_revenue:,.0f}</div>
                            <div class="metric-label">Total Revenue</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">{total_transactions}</div>
                            <div class="metric-label">Transactions</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">{total_units}</div>
                            <div class="metric-label">Units Sold</div>
                        </div>
                    </div>
                    
                    <div class="section">
                        <h3>🏆 Top 5 Products Today</h3>
                        <ol>
                            {top_products_html}
                        </ol>
                    </div>
                    
                    <p style="text-align: center; margin-top: 20px;">
                        <a href="https://kirana-predict.streamlit.app/" style="background-color: #1976d2; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                            View Detailed Analytics
                        </a>
                    </p>
                </div>
                <div class="footer">
                    <p>Kirana-Predict Daily Report | Automated Summary</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def send_low_stock_alerts(self, inventory_data: List[Dict]) -> int:
        """Send alerts for all low stock items"""
        alerts_sent = 0

        for item in inventory_data:
            if item["days_remaining"] < 7:
                html = self.create_low_stock_alert(
                    product_name=item["product_name"],
                    current_stock=item["current_stock"],
                    days_remaining=item["days_remaining"],
                    avg_daily_sales=item["avg_daily_sales"],
                )

                urgency = (
                    "CRITICAL" if item["days_remaining"] < 3 else "LOW STOCK"
                )
                subject = f"🚨 {urgency}: {item['product_name']} - {item['days_remaining']:.1f} days remaining"

                if self.send_email(subject, html):
                    alerts_sent += 1

        return alerts_sent

    def send_daily_summary_email(self, sales_df: pd.DataFrame) -> bool:
        """Send daily sales summary"""
        html = self.create_daily_summary(sales_df)
        subject = f"📊 Daily Sales Summary - {datetime.now().strftime('%d %b %Y')}"
        return self.send_email(subject, html)


if __name__ == "__main__":
    print("🧪 Testing Email Alert Manager...\n")

    email_manager = EmailAlertManager()

    print(f"Email Enabled: {email_manager.enabled}")
    print(f"Service: {email_manager.service}")
    print(f"Sender: {email_manager.sender}")
    print(f"Recipients: {email_manager.recipients}")

    print("\n📧 Sending test low stock alert...")
    test_html = email_manager.create_low_stock_alert(
        product_name="Rice 1kg",
        current_stock=15,
        days_remaining=2.5,
        avg_daily_sales=6.0,
    )

    success = email_manager.send_email(
        subject="🚨 TEST: Low Stock Alert - Rice 1kg",
        html_body=test_html,
    )

    if success:
        print("✅ Test email sent successfully!")
    else:
        print("❌ Test email failed. Check configuration.")

