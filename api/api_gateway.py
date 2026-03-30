"""
api/api_gateway.py — Enhanced POS Webhook Gateway with Inventory Sync
======================================================================
Receives sale webhooks from POS billing counter and auto-updates inventory.

Endpoints:
  POST /webhook/sale          — Record sale + deduct stock
  POST /webhook/stock-inward  — Record purchase + add stock
  POST /webhook/transfer      — Inter-store transfer
  GET  /inventory/stock/{store_code}      — Current inventory
  GET  /inventory/low-stock/{store_code}  — Low-stock items
  GET  /inventory/health/{store_code}     — Health score
  GET  /health                            — API health check
"""

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
import os
from dotenv import load_dotenv

# Import managers
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database_manager import KiranaDatabase
from core.inventory_manager import InventoryManager

load_dotenv()

# ════════════════════════════════════════════════════════════════════
# FASTAPI APP SETUP
# ════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Kirana-Predict POS Gateway",
    description="Real-time webhook receiver for POS systems with automatic inventory sync",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # In production, specify POS system domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize managers
db = KiranaDatabase()
inventory = InventoryManager()

# API Key
API_KEY = os.getenv("WEBHOOK_API_KEY", "your_secret_key_12345")


# ════════════════════════════════════════════════════════════════════
# REQUEST MODELS
# ════════════════════════════════════════════════════════════════════

class SaleWebhook(BaseModel):
    """Incoming sale webhook from POS."""
    transaction_id: str = Field(..., description="Unique transaction ID from POS")
    store_code: str = Field(..., description="Store identifier (e.g., STORE001)")
    product_name: str = Field(..., description="Product name")
    quantity: int = Field(..., gt=0, description="Quantity sold")
    unit_price: float = Field(..., gt=0, description="Price per unit")
    total_amount: Optional[float] = Field(None, description="Total sale amount")
    payment_method: str = Field(default="Cash", description="Payment method")
    customer_name: Optional[str] = Field(default="Walk-in", description="Customer name")
    category: Optional[str] = Field(default=None, description="Product category")
    transaction_date: Optional[str] = Field(None, description="ISO timestamp")

    @validator('total_amount', always=True)
    def calculate_total(cls, v, values):
        if v is None and 'quantity' in values and 'unit_price' in values:
            return values['quantity'] * values['unit_price']
        return v

    @validator('transaction_date', always=True)
    def set_transaction_date(cls, v):
        return v if v else datetime.now().isoformat()

    class Config:
        schema_extra = {
            "example": {
                "transaction_id": "TXN_20260330_001",
                "store_code": "STORE001",
                "product_name": "Aashirvaad Atta 5kg",
                "quantity": 2,
                "unit_price": 299.0,
                "payment_method": "UPI",
            }
        }


class StockInward(BaseModel):
    """Incoming stock/purchase."""
    store_code: str
    product_name: str
    quantity: int = Field(..., gt=0)
    unit_cost: float = Field(..., gt=0)
    supplier_name: Optional[str] = None
    invoice_number: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "store_code": "STORE001",
                "product_name": "Aashirvaad Atta 5kg",
                "quantity": 50,
                "unit_cost": 280.0,
                "supplier_name": "ITC Limited",
                "invoice_number": "INV-2026-001",
            }
        }


class TransferRequest(BaseModel):
    """Inter-store stock transfer."""
    product_name: str
    from_store: str
    to_store: str
    quantity: int = Field(..., gt=0)
    reason: Optional[str] = ""

    class Config:
        schema_extra = {
            "example": {
                "product_name": "Aashirvaad Atta 5kg",
                "from_store": "STORE001",
                "to_store": "STORE002",
                "quantity": 20,
                "reason": "Stock balancing",
            }
        }


# ════════════════════════════════════════════════════════════════════
# SECURITY
# ════════════════════════════════════════════════════════════════════

def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key.")
    return x_api_key


# ════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    return {
        "service": "Kirana-Predict POS Gateway",
        "version": "3.0.0",
        "status": "online",
        "features": [
            "Real-time sale recording",
            "Automatic inventory deduction",
            "Low stock alerts",
            "Inter-store transfers",
            "Multi-store support",
        ],
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": "connected",
        "inventory_system": "active",
    }


# ── SALE WEBHOOK ──────────────────────────────────────────────────

@app.post("/webhook/sale")
async def receive_sale_webhook(
    sale: SaleWebhook,
    api_key: str = Depends(verify_api_key),
):
    """
    PRIMARY ENDPOINT: Record sale from POS + auto-deduct inventory.

    Flow:
      1. Insert sale row into `sales` table
      2. Deduct stock from `inventory` via InventoryManager
      3. Return updated stock level + low-stock flag
    """
    try:
        # 1. Record the sale
        sale_data = {
            'transaction_id': sale.transaction_id,
            'store_code': sale.store_code,
            'product_name': sale.product_name,
            'quantity': sale.quantity,
            'unit_price': sale.unit_price,
            'total_amount': sale.total_amount,
            'category': sale.category,
            'transaction_date': sale.transaction_date,
            'data_source': 'pos_webhook',
        }
        db.add_sale(sale_data, source='pos_webhook')

        # 2. Deduct inventory
        success, message = inventory.deduct_stock_on_sale(
            product_name=sale.product_name,
            store_code=sale.store_code,
            quantity=sale.quantity,
            transaction_id=sale.transaction_id,
            unit_price=sale.unit_price,
        )

        # 3. Get updated stock
        stock_info = inventory.get_current_stock(sale.product_name, sale.store_code)
        current_stock = stock_info['current_stock'] if stock_info else 0
        reorder_pt = stock_info.get('reorder_point', 10) if stock_info else 10
        is_low = current_stock <= reorder_pt

        return {
            "status": "success",
            "message": "Sale recorded and inventory updated",
            "transaction_id": sale.transaction_id,
            "product": sale.product_name,
            "quantity_sold": sale.quantity,
            "inventory": {
                "current_stock": current_stock,
                "is_low_stock": is_low,
                "message": message,
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing sale: {e}")


# ── STOCK INWARD WEBHOOK ─────────────────────────────────────────

@app.post("/webhook/stock-inward")
async def receive_stock_inward(
    stock: StockInward,
    api_key: str = Depends(verify_api_key),
):
    """Record new stock arrival and update inventory."""
    try:
        success, message = inventory.add_stock_on_purchase(
            product_name=stock.product_name,
            store_code=stock.store_code,
            quantity=stock.quantity,
            unit_cost=stock.unit_cost,
            reference_id=stock.invoice_number,
        )

        stock_info = inventory.get_current_stock(stock.product_name, stock.store_code)
        current_stock = stock_info['current_stock'] if stock_info else 0

        return {
            "status": "success",
            "message": message,
            "product": stock.product_name,
            "quantity_added": stock.quantity,
            "inventory": {"current_stock": current_stock},
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


# ── TRANSFER WEBHOOK ─────────────────────────────────────────────

@app.post("/webhook/transfer")
async def create_transfer(
    transfer: TransferRequest,
    api_key: str = Depends(verify_api_key),
):
    """Atomic inter-store stock transfer."""
    try:
        success, message = inventory.transfer_stock(
            product_name=transfer.product_name,
            from_store=transfer.from_store,
            to_store=transfer.to_store,
            quantity=transfer.quantity,
            reason=transfer.reason or "",
        )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        return {
            "status": "success",
            "message": message,
            "product": transfer.product_name,
            "from_store": transfer.from_store,
            "to_store": transfer.to_store,
            "quantity": transfer.quantity,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


# ── INVENTORY READ ENDPOINTS ─────────────────────────────────────

@app.get("/inventory/stock/{store_code}")
async def get_store_inventory(
    store_code: str,
    api_key: str = Depends(verify_api_key),
):
    """Current inventory for a store."""
    try:
        stock_df = inventory.get_all_stock(store_code)

        if stock_df.empty:
            return {"store_code": store_code, "items": [], "total_products": 0}

        items = stock_df.to_dict('records')
        return {
            "store_code": store_code,
            "total_products": len(items),
            "total_units": int(stock_df['current_stock'].sum()),
            "items": items,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@app.get("/inventory/low-stock/{store_code}")
async def get_low_stock(
    store_code: str,
    api_key: str = Depends(verify_api_key),
):
    """Items needing reorder at a store."""
    try:
        low_df = inventory.get_low_stock_items(store_code)

        if low_df.empty:
            return {
                "store_code": store_code,
                "message": "All products have sufficient stock ✅",
                "items": [],
            }

        return {
            "store_code": store_code,
            "alert": f"⚠️ {len(low_df)} products need reordering",
            "items": low_df.to_dict('records'),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@app.get("/inventory/health/{store_code}")
async def get_health_score(
    store_code: str,
    api_key: str = Depends(verify_api_key),
):
    """Inventory health score for a store."""
    try:
        health = inventory.get_inventory_health_score(store_code)
        return {"store_code": store_code, **health}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@app.get("/inventory/suggestions/{store_code}")
async def get_reorder_suggestions(
    store_code: str,
    priority: str = "all",
    api_key: str = Depends(verify_api_key),
):
    """Reorder suggestions for a store."""
    try:
        suggestions = inventory.generate_reorder_suggestions(
            store_code=store_code, priority=priority,
        )

        if suggestions.empty:
            return {
                "store_code": store_code,
                "message": "No reorder suggestions — all stock healthy ✅",
                "count": 0,
                "suggestions": [],
            }

        return {
            "store_code": store_code,
            "count": len(suggestions),
            "suggestions": suggestions.to_dict('records'),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


# ════════════════════════════════════════════════════════════════════
# RUN SERVER
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("🚀 KIRANA-PREDICT POS GATEWAY v3.0")
    print("=" * 60)
    print(f"📡 Starting server …")
    print(f"🔑 API Key: {API_KEY[:8]}{'*' * (len(API_KEY) - 8)}")
    print(f"📝 Docs: http://localhost:8000/docs")
    print("=" * 60)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )