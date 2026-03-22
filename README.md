# 📦 Kirana-Predict Pro

> AI-powered Inventory Forecasting & Real-Time POS Integration for Indian Kirana stores.  
> Built to prevent stock-outs, reduce waste, and enable multi-store management.

---

## 🏗️ Project Structure

```
Kirana Store/
├── main.py                     # 🚀 Main Streamlit entry point
├── requirements.txt            # Python dependencies
├── .env                        # Local environment secrets (not committed)
│
├── core/                       # Business Logic Layer
│   ├── database_connection.py  # Supabase client setup (local + cloud)
│   ├── database_manager.py     # CRUD operations, Auth, RBAC
│   ├── ml_engine.py            # Prophet-based demand forecasting
│   ├── email_manager.py        # SendGrid email alert integration
│   └── watchdog_sync.py        # File-system watcher for auto data sync
│
├── api/                        # REST API Layer
│   └── api_gateway.py          # FastAPI POS webhook server
│
├── app/                        # Streamlit UI Modules
│   └── store_management_page.py # Multi-store management UI
│
├── scripts/                    # Legacy / Utility Scripts
│   ├── analysis.py             # Exploratory sales analysis
│   ├── prediction.py           # CLI-based burn rate prediction
│   ├── main.py                 # Old CLI entry point
│   └── helpers.py              # CSV data loader helper
│
├── data/                       # Raw / processed data files
├── logs/                       # Application log output
└── billing_exports/            # Exported billing data
```

---

## 🚀 Features

- **🔐 User Authentication & RBAC** – Supabase Auth login with Admin/Staff role enforcement
- **📊 Sales Analytics** – Top products, weekly trends, store-level breakdowns
- **🔮 AI Demand Forecasting** – Prophet (Meta) ML model for next-week predictions
- **🏪 Multi-Store Management** – Add, update, and compare multiple store locations
- **📧 Email Alerts** – SendGrid-powered low-stock email notifications
- **⚡ Real-Time POS Integration** – FastAPI webhook endpoint `/webhook/sale` for live POS data ingestion
- **📤 Export** – Download sales data as CSV or Excel

---

## 🛠️ Tech Stack

| Layer      | Technology         |
|------------|--------------------|
| Frontend   | Streamlit          |
| Backend    | FastAPI + Uvicorn  |
| Database   | Supabase (PostgreSQL) |
| ML Engine  | Prophet (Meta)     |
| Auth       | Supabase Auth      |
| Alerts     | SendGrid           |
| Language   | Python 3.12+       |

---

## ▶️ Running Locally

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file in the project root:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key
SENDGRID_API_KEY=your_sendgrid_key
```

### 3. Run the Streamlit App
```bash
python -m streamlit run main.py
```

### 4. Run the POS API Gateway (optional, separate terminal)
```bash
python -m uvicorn api.api_gateway:app --reload
```
Access the interactive API docs at: `http://127.0.0.1:8000/docs`

---

## 🔐 Setting Up Auth (First Time)

1. In Supabase → **Authentication** → create a user with email + password
2. In Supabase → **SQL Editor**, run:
```sql
create table if not exists user_roles (
  id serial primary key,
  user_id uuid references auth.users not null,
  role text not null check (role in ('Admin', 'Staff'))
);

-- Assign Admin role to your user:
insert into user_roles (user_id, role)
select id, 'Admin' from auth.users where email = 'your@email.com';
```

---

## 📡 POS Webhook API

**Endpoint:** `POST http://localhost:8000/webhook/sale`

**Sample Payload:**
```json
{
  "product_name": "Aashirvaad Atta 5kg",
  "quantity": 3,
  "unit_price": 299.0,
  "store_code": "STORE001"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Sale recorded successfully",
  "transaction_id": "TXN_1773498345"
}
```
