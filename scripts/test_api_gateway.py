"""
test_api_gateway.py
===================
Quick integration test for the Kirana-Predict API Gateway.

Usage:
    1. Start the gateway first:
       uvicorn api.api_gateway:app --reload        (from project root)

    2. In a second terminal, run this script:
       python scripts/test_api_gateway.py

Requires: httpx (already in requirements.txt)
"""

import httpx
import sys
import os

# ------------------------------------------------------------------
# CONFIG  – must match what's in your .env
# ------------------------------------------------------------------
BASE_URL  = "http://localhost:8000"
API_KEY   = os.getenv("POS_API_KEY", "kirana-predict-secret-key-2024")

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
}

PASS = "✅ PASS"
FAIL = "❌ FAIL"

errors = 0


def check(label: str, condition: bool, extra: str = ""):
    global errors
    status = PASS if condition else FAIL
    if not condition:
        errors += 1
    print(f"  {status}  {label}" + (f"  →  {extra}" if extra else ""))


# ------------------------------------------------------------------
# TESTS
# ------------------------------------------------------------------

print("\n" + "=" * 55)
print("  Kirana-Predict API Gateway – Integration Test Suite")
print("=" * 55 + "\n")

with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:

    # 1. Root health check (no auth required)
    print("📌 Test 1: Root endpoint")
    try:
        r = client.get("/")
        check("Status 200",   r.status_code == 200, str(r.status_code))
        check("Body has 'service' key", "service" in r.json())
    except Exception as e:
        print(f"  {FAIL}  Could not connect: {e}")
        print("\n⚠️  Make sure the gateway is running:\n"
              "    uvicorn api.api_gateway:app --reload\n")
        sys.exit(1)

    # 2. /health endpoint
    print("\n📌 Test 2: /health endpoint")
    r = client.get("/health")
    check("Status 200 or 503", r.status_code in (200, 503), str(r.status_code))
    if r.status_code == 200:
        check("Database connected", r.json().get("database") == "connected")
    else:
        print("  ⚠️  Database unreachable (check Supabase credentials)")

    # 3. /webhook/sale – missing API key  → 422 (header required) or 401
    print("\n📌 Test 3: Reject request without API key")
    r = client.post(
        "/webhook/sale",
        json={"product_name": "Test", "quantity": 1, "unit_price": 10.0},
    )
    check(
        "Rejected without X-API-Key",
        r.status_code in (401, 422),
        f"got {r.status_code}",
    )

    # 4. /webhook/sale – wrong API key  → 401
    print("\n📌 Test 4: Reject request with wrong API key")
    r = client.post(
        "/webhook/sale",
        json={"product_name": "Test", "quantity": 1, "unit_price": 10.0},
        headers={**HEADERS, "X-API-Key": "wrong-key"},
    )
    check("Rejected with bad key", r.status_code == 401, f"got {r.status_code}")

    # 5. /webhook/sale – valid request
    print("\n📌 Test 5: Accept valid sale (writes to Supabase)")
    payload = {
        "product_name": "Tata Salt 1kg [API-TEST]",
        "quantity":     2,
        "unit_price":   22.5,
        "store_code":   "STORE001",
        "category":     "Grocery",
    }
    r = client.post("/webhook/sale", json=payload, headers=HEADERS)
    check("Status 201", r.status_code == 201, str(r.status_code))
    if r.status_code == 201:
        body = r.json()
        check("Status = 'success'",   body.get("status") == "success")
        check("transaction_id present", "transaction_id" in body)
        check("total_amount = 45.0",  body.get("total_amount") == 45.0,
              str(body.get("total_amount")))
    else:
        print(f"  Detail: {r.text[:200]}")
        errors += 1

    # 6. /webhook/sale – invalid payload (quantity = 0)
    print("\n📌 Test 6: Reject invalid payload (quantity < 1)")
    r = client.post(
        "/webhook/sale",
        json={"product_name": "Bad", "quantity": 0, "unit_price": 10.0},
        headers=HEADERS,
    )
    check("Status 422 for bad payload", r.status_code == 422, str(r.status_code))

# ------------------------------------------------------------------
print("\n" + "=" * 55)
if errors == 0:
    print("  🎉  All tests passed! API Gateway is working correctly.")
else:
    print(f"  ⚠️  {errors} test(s) failed. Review the output above.")
print("=" * 55 + "\n")
