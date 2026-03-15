"""
api_gateway.py - Kirana-Predict POS Integration Gateway
======================================================
A FastAPI-based webhook receiver that allows external POS
systems to push sales transactions directly into Supabase.

Run with:
    uvicorn api.api_gateway:app --reload            (from project root)
    uvicorn api_gateway:app --reload                (from within api/ folder)

Test with:
    curl -X POST http://localhost:8000/webhook/sale \
         -H "Content-Type: application/json" \
         -H "X-API-Key: your_api_key_here" \
         -d '{"product_name":"Tata Salt 1kg","quantity":5,"unit_price":22.0}'
"""

import sys
import os
from datetime import datetime
from typing import Optional

# ── path fix so this file can be run from inside api/ OR from project root ──
_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
if _root not in sys.path:
    sys.path.insert(0, _root)

# ── load .env BEFORE importing KiranaDatabase ──
from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from fastapi import FastAPI, HTTPException, Header, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from core.database_manager import KiranaDatabase

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
# API Key for authenticating incoming webhook requests.
# Set POS_API_KEY in your .env file.
# If not set, key-checking is still enforced – callers must pass
# the literal value "CHANGE_ME_IN_ENV" (a reminder to configure it).
POS_API_KEY: str = os.getenv("POS_API_KEY", "CHANGE_ME_IN_ENV")

# ─────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────
app = FastAPI(
    title="Kirana-Predict POS Integration API",
    description=(
        "Receives real-time sale events from POS systems and "
        "writes them to the Kirana-Predict Supabase database."
    ),
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow cross-origin requests from POS terminals / local frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Single shared DB connection (thread-safe for async I/O)
_db: Optional[KiranaDatabase] = None


def get_db() -> KiranaDatabase:
    global _db
    if _db is None:
        _db = KiranaDatabase()
    return _db


# ─────────────────────────────────────────────
# SECURITY DEPENDENCY
# ─────────────────────────────────────────────

async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """Dependency: validates the X-API-Key header on protected endpoints."""
    if x_api_key != POS_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Set the X-API-Key header.",
        )
    return x_api_key


# ─────────────────────────────────────────────
# PAYLOAD MODEL
# ─────────────────────────────────────────────

class SalePayload(BaseModel):
    """
    Expected JSON body for the /webhook/sale endpoint.
    All fields marked with * are required.
    """
    product_name: str = Field(..., example="Aashirvaad Atta 5kg")
    quantity: int = Field(..., ge=1, example=3)
    unit_price: float = Field(..., gt=0, example=255.0)

    # Optional enrichment fields
    store_code: Optional[str] = Field(default="STORE001", example="STORE002")
    category: Optional[str] = Field(default=None, example="Groceries")
    transaction_id: Optional[str] = Field(default=None, example="POS-TXN-20240315-001")
    transaction_date: Optional[str] = Field(
        default=None,
        example="2024-03-15T14:30:00",
        description="ISO 8601 datetime. Defaults to current server time if omitted.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "product_name": "Tata Salt 1kg",
                "quantity": 5,
                "unit_price": 22.0,
                "store_code": "STORE001",
                "category": "Grocery",
            }
        }


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.get("/", tags=["Status"])
def root():
    """Public health-check endpoint – no auth required."""
    return {
        "service": "Kirana-Predict API Gateway",
        "status": "running",
        "version": "1.1.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["Status"])
def health_check(db: KiranaDatabase = Depends(get_db)):
    """
    Extended health check: verifies DB connectivity.
    Returns 503 if the database is unreachable.
    """
    try:
        # Lightweight probe: just fetch a single row
        db.supabase.table("sales").select("id").limit(1).execute()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unreachable: {str(e)}",
        )


@app.post(
    "/webhook/sale",
    tags=["POS Webhook"],
    summary="Record a sale from a POS terminal",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
async def receive_sale(
    sale: SalePayload,
    db: KiranaDatabase = Depends(get_db),
):
    """
    Accepts a sale payload from an external POS system and
    inserts it into the Supabase `sales` table.

    **Authentication:** Requires the `X-API-Key` header matching
    the `POS_API_KEY` value set in your `.env` file.
    """
    try:
        sale_dict = sale.model_dump()

        # Derive total_amount
        sale_dict["total_amount"] = round(
            sale_dict["quantity"] * sale_dict["unit_price"], 2
        )

        # Default transaction_date to now if not supplied
        if not sale_dict.get("transaction_date"):
            sale_dict["transaction_date"] = datetime.now().isoformat()

        # Strip None values to avoid Supabase schema type errors
        sale_dict = {k: v for k, v in sale_dict.items() if v is not None}

        print(
            f"📥 POS Webhook | {sale_dict['product_name']} "
            f"x {sale_dict['quantity']} @ ₹{sale_dict['unit_price']} "
            f"| store={sale_dict.get('store_code', '?')}"
        )

        result = db.add_sale(sale_dict, source="pos_api")

        return {
            "status": "success",
            "message": "Sale recorded successfully.",
            "transaction_id": result.get("transaction_id", "N/A"),
            "total_amount": sale_dict["total_amount"],
        }

    except Exception as exc:
        print(f"❌ Webhook error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


# ─────────────────────────────────────────────
# ENTRY POINT (run directly)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("🚀 Starting Kirana-Predict API Gateway on http://localhost:8000")
    print("   Swagger UI → http://localhost:8000/docs")
    print(f"   POS_API_KEY = {'(set)' if POS_API_KEY != 'CHANGE_ME_IN_ENV' else '⚠️  NOT SET – using default placeholder'}")
    uvicorn.run("api.api_gateway:app", host="0.0.0.0", port=8000, reload=True)
