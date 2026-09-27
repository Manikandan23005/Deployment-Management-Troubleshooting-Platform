from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import uuid
import datetime
import random
from .telemetry import instrument_app

app = FastAPI(
    title="Payment Service",
    description="Enterprise Payment Gateway & Transaction Processing Microservice",
    version="1.0.0"
)
instrument_app(app, "payment-service")

@app.get("/healthz")
def healthz():
    return {"status": "healthy", "service": "payment"}

class PaymentRequest(BaseModel):
    amount: float = Field(..., description="Transaction amount")
    method: Optional[str] = Field("CARD", description="Payment method: UPI, CARD, NETBANKING, COD, EMI")
    order_id: Optional[str] = Field(None, description="Linked Order Identifier")
    customer_name: Optional[str] = Field("Customer", description="Payer full name")
    upi_id: Optional[str] = Field(None, description="UPI Virtual Payment Address (e.g. user@okhdfc)")
    card_last4: Optional[str] = Field("4242", description="Last 4 digits of card")
    bank_name: Optional[str] = Field(None, description="Bank Name for NetBanking")

class LegacyChargeRequest(BaseModel):
    order_id: Optional[Any] = None
    amount: float
    currency: Optional[str] = "USD"

TRANSACTIONS: Dict[str, Dict[str, Any]] = {}

@app.post("/pay")
def process_payment(req: PaymentRequest):
    if req.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Transaction amount must be greater than zero."
        )

    txn_id = f"TXN-NEXUS-{datetime.datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # Realistic method details
    method_details = {}
    if req.method == "UPI":
        method_details = {"provider": "UPI Auto-Pay", "vpa": req.upi_id or "customer@nexusupi"}
    elif req.method == "CARD":
        method_details = {"network": "Visa/MasterCard", "last4": req.card_last4 or "4242"}
    elif req.method == "NETBANKING":
        method_details = {"bank": req.bank_name or "HDFC Bank Secure Portal"}
    elif req.method == "COD":
        method_details = {"type": "Pay on Delivery (Cash/UPI)"}

    txn_record = {
        "transaction_id": txn_id,
        "order_id": req.order_id or f"ORD-{uuid.uuid4().hex[:6].upper()}",
        "amount": round(req.amount, 2),
        "currency": "USD",
        "method": req.method or "CARD",
        "method_details": method_details,
        "status": "success",
        "customer_name": req.customer_name,
        "timestamp": timestamp,
        "gateway_ref": f"REF-GATEWAY-{random.randint(100000, 999999)}"
    }
    
    TRANSACTIONS[txn_id] = txn_record
    return txn_record

@app.post("/charge")
def charge_legacy(req: LegacyChargeRequest):
    if req.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Transaction amount must be positive."
        )
    txn_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
    return {
        "status": "success",
        "transaction_id": txn_id,
        "amount": req.amount,
        "currency": req.currency or "USD"
    }

@app.get("/transactions/{txn_id}")
def get_transaction(txn_id: str):
    if txn_id not in TRANSACTIONS:
        raise HTTPException(status_code=404, detail="Transaction reference not found.")
    return TRANSACTIONS[txn_id]

@app.get("/transactions")
def list_transactions() -> List[Dict[str, Any]]:
    return list(TRANSACTIONS.values())

@app.post("/refund")
def process_refund(transaction_id: str, amount: Optional[float] = None):
    if transaction_id not in TRANSACTIONS:
        raise HTTPException(status_code=404, detail="Transaction not found for refund.")
        
    txn = TRANSACTIONS[transaction_id]
    refund_amt = amount or txn["amount"]
    txn["status"] = "refunded"
    txn["refunded_amount"] = refund_amt
    txn["refund_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    return {
        "success": True,
        "transaction_id": transaction_id,
        "refunded_amount": refund_amt,
        "message": f"Refund of ${refund_amt} successfully initiated to original payment source."
    }