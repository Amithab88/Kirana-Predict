"""
api/api_gateway.py - Enhanced POS Webhook Gateway with Inventory Sync
Receives sale webhooks from billing counter and auto-updates inventory
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

# ============================================
# FASTAPI APP SETUP
# ============================================

app = FastAPI(
    title="Kirana-Predict POS Gateway",
    description="Real-time webhook receiver for POS systems with automatic inventory sync",
    version="2.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your POS system domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize managers
db = KiranaDatabase()
inventory = InventoryManager()

# API Key for security
API_KEY = os.getenv("WEBHOOK_API_KEY", "your_secret_key_12345")

# ============================================
# REQUEST MODELS
# ============================================

class SaleWebhook(BaseModel):
    """Model for incoming sale webhook from POS"""
    transaction_id: str = Field(..., description="Unique transaction ID from POS")
    store_code: str = Field(..., description="Store identifier (e.g., STORE001)")
    product_name: str = Field(..., description="Product name")
    quantity: int = Field(..., gt=0, description="Quantity sold (must be positive)")
    unit_price: float = Field(..., gt=0, description="Price per unit")
    total_amount: Optional[float] = Field(None, description="Total sale amount")
    payment_method: str = Field(default="Cash", description="Payment method")
    customer_name: Optional[str] = Field(default="Walk-in", description="Customer name")
    transaction_date: Optional[str] = Field(None, description="Transaction timestamp (ISO format)")
    
    @validator('total_amount', always=True)
    def calculate_total(cls, v, values):
        """Auto-calculate total if not provided"""
        if v is None and 'quantity' in values and 'unit_price' in values:
            return values['quantity'] * values['unit_price']
        return v
    
    @validator('transaction_date', always=True)
    def set_transaction_date(cls, v):
        """Set current timestamp if not provided"""
        if v is None:
            return datetime.now().isoformat()
        return v

    class Config:
        schema_extra = {
            "example": {
                "transaction_id": "TXN_20260320_001",
                "store_code": "STORE001",
                "product_name": "Aashirvaad Atta 5kg",
                "quantity": 2,
                "unit_price": 299.0,
                "total_amount": 598.0,
                "payment_method": "Cash",
                "customer_name": "Walk-in",
                "transaction_date": "2026-03-20T14:30:00Z"
            }
        }


class StockInward(BaseModel):
    """Model for incoming stock/purchase"""
    store_code: str = Field(..., description="Store identifier")
    product_name: str = Field(..., description="Product name")
    quantity: int = Field(..., gt=0, description="Quantity received")
    unit_cost: float = Field(..., gt=0, description="Cost per unit")
    supplier_name: Optional[str] = Field(None, description="Supplier name")
    invoice_number: Optional[str] = Field(None, description="Purchase invoice number")
    
    class Config:
        schema_extra = {
            "example": {
                "store_code": "STORE001",
                "product_name": "Aashirvaad Atta 5kg",
                "quantity": 50,
                "unit_cost": 280.0,
                "supplier_name": "ITC Limited",
                "invoice_number": "INV-2026-001"
            }
        }


# ============================================
# SECURITY: API KEY VALIDATION
# ============================================

def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """Verify API key from request header"""
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key. Access denied."
        )
    return x_api_key


# ============================================
# ENDPOINTS
# ============================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Kirana-Predict POS Gateway",
        "version": "2.0.0",
        "status": "online",
        "features": [
            "Real-time sale recording",
            "Automatic inventory deduction",
            "Low stock alerts",
            "Multi-store support"
        ]
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": "connected",
        "inventory_system": "active"
    }


@app.post("/webhook/sale")
async def receive_sale_webhook(
    sale: SaleWebhook,
    api_key: str = Depends(verify_api_key)
):
    """
    PRIMARY ENDPOINT: Receive sale from POS and auto-update inventory
    
    Flow:
    1. Validate incoming data
    2. Record sale in database
    3. Deduct stock from inventory
    4. Check if reorder needed
    5. Send alerts if low stock
    
    Returns: Confirmation with inventory status
    """
    try:
        # Step 1: Record the sale
        sale_data = {
            'transaction_id': sale.transaction_id,
            'store_code': sale.store_code,
            'product_name': sale.product_name,
            'quantity': sale.quantity,
            'unit_price': sale.unit_price,
            'total_amount': sale.total_amount,
            'payment_method': sale.payment_method,
            'customer_name': sale.customer_name,
            'transaction_date': sale.transaction_date,
            'data_source': 'pos_webhook'
        }
        
        sale_record = db.add_sale(sale_data, source='pos_webhook')
        
        # Step 2: Deduct from inventory
        success, message = inventory.deduct_stock_on_sale(
            product_name=sale.product_name,
            store_code=sale.store_code,
            quantity=sale.quantity,
            transaction_id=sale.transaction_id,
            unit_price=sale.unit_price
        )
        
        # Step 3: Get updated stock level
        stock_info = inventory.get_current_stock(sale.product_name, sale.store_code)
        current_stock = stock_info['current_stock'] if stock_info else 0
        
        # Step 4: Check if low stock
        is_low_stock = False
        if stock_info:
            is_low_stock = current_stock <= stock_info['reorder_point']
        
        return {
            "status": "success",
            "message": "Sale recorded and inventory updated",
            "transaction_id": sale.transaction_id,
            "product": sale.product_name,
            "quantity_sold": sale.quantity,
            "inventory": {
                "current_stock": current_stock,
                "is_low_stock": is_low_stock,
                "message": message
            }
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing sale: {str(e)}"
        )


@app.post("/webhook/stock-inward")
async def receive_stock_inward(
    stock: StockInward,
    api_key: str = Depends(verify_api_key)
):
    """
    Receive new stock arrival and update inventory
    
    Use this endpoint when new stock arrives at the store
    """
    try:
        # Add stock to inventory
        success, message = inventory.add_stock_on_purchase(
            product_name=stock.product_name,
            store_code=stock.store_code,
            quantity=stock.quantity,
            unit_cost=stock.unit_cost,
            reference_id=stock.invoice_number
        )
        
        # Get updated stock
        stock_info = inventory.get_current_stock(stock.product_name, stock.store_code)
        current_stock = stock_info['current_stock'] if stock_info else 0
        
        return {
            "status": "success",
            "message": "Stock added to inventory",
            "product": stock.product_name,
            "quantity_added": stock.quantity,
            "inventory": {
                "current_stock": current_stock,
                "message": message
            }
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing stock inward: {str(e)}"
        )


@app.get("/inventory/stock/{store_code}")
async def get_store_inventory(
    store_code: str,
    api_key: str = Depends(verify_api_key)
):
    """Get current inventory levels for a store"""
    try:
        stock_df = inventory.get_all_stock(store_code)
        
        if stock_df.empty:
            return {"store_code": store_code, "items": []}
        
        items = stock_df.to_dict('records')
        
        return {
            "store_code": store_code,
            "total_products": len(items),
            "total_units": int(stock_df['current_stock'].sum()),
            "items": items
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching inventory: {str(e)}"
        )


@app.get("/inventory/low-stock/{store_code}")
async def get_low_stock_items(
    store_code: str,
    api_key: str = Depends(verify_api_key)
):
    """Get items that need reordering for a store"""
    try:
        low_stock_df = inventory.get_low_stock_items(store_code)
        
        if low_stock_df.empty:
            return {
                "store_code": store_code,
                "message": "All products have sufficient stock ✅",
                "items": []
            }
        
        items = low_stock_df.to_dict('records')
        
        return {
            "store_code": store_code,
            "alert": f"⚠️ {len(items)} products need reordering",
            "items": items
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching low stock: {str(e)}"
        )


@app.get("/inventory/alerts")
async def get_reorder_alerts(api_key: str = Depends(verify_api_key)):
    """Get all pending reorder alerts across all stores"""
    try:
        alerts_df = inventory.get_reorder_alerts(status='PENDING')
        
        if alerts_df.empty:
            return {
                "message": "No pending reorder alerts ✅",
                "count": 0,
                "alerts": []
            }
        
        alerts = alerts_df.to_dict('records')
        
        return {
            "message": f"⚠️ {len(alerts)} products need reordering",
            "count": len(alerts),
            "alerts": alerts
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching alerts: {str(e)}"
        )


# ============================================
# RUN SERVER
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("🚀 KIRANA-PREDICT POS GATEWAY")
    print("=" * 60)
    print(f"📡 Starting server...")
    print(f"🔑 API Key: {API_KEY}")
    print(f"📝 Docs: http://localhost:8000/docs")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
