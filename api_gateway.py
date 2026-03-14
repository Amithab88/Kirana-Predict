from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import uvicorn
from database_manager import KiranaDatabase

# Initialize FastAPI App
app = FastAPI(title="Kirana-Predict POS Integration API")

# Initialize Database connection
db = KiranaDatabase()

class SalePayload(BaseModel):
    """Data model matching the expected incoming POS webhook payload"""
    product_name: str
    quantity: int
    unit_price: float
    store_code: Optional[str] = "STORE001" # Default to main store if not provided
    transaction_id: Optional[str] = None
    transaction_date: Optional[str] = None

@app.get("/")
def read_root():
    return {"status": "Kirana-Predict API Gateway is running!"}

@app.post("/webhook/sale")
async def receive_sale(sale: SalePayload):
    """
    Endpoint to receive real-time sales from a POS system.
    """
    try:
        # Convert Pydantic model to dictionary
        sale_data = sale.model_dump()
        
        # Ensure total_amount is calculated if missing
        sale_data['total_amount'] = sale_data['quantity'] * sale_data['unit_price']
        
        # Strip out any keys that have a value of None to prevent Supabase schema errors
        safe_data = {k: v for k, v in sale_data.items() if v is not None}
        
        # If transaction date is missing, use current time
        if "transaction_date" not in safe_data:
            safe_data["transaction_date"] = datetime.now().isoformat()
            
        print(f"📥 Received POS Webhook: {safe_data['product_name']} x {safe_data['quantity']}")
            
        # Add to Supabase
        result = db.add_sale(safe_data, source='pos_api')
        
        if result:
            return {
                "status": "success",
                "message": "Sale recorded successfully",
                "transaction_id": result.get('transaction_id', 'Unknown')
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to insert into database")

    except Exception as e:
        print(f"❌ Webhook Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    print("🚀 Starting Kirana-Predict API Gateway on port 8000...")
    uvicorn.run("api_gateway:app", host="0.0.0.0", port=8000, reload=True)
