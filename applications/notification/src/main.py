from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import datetime
import uuid
from .telemetry import instrument_app

app = FastAPI(
    title="Notification Service",
    description="Enterprise Multi-Channel Order & Alert Dispatch Microservice",
    version="1.0.0"
)
instrument_app(app, "notification-service")

@app.get("/healthz")
def healthz():
    return {"status": "healthy", "service": "notification"}

class NotifyRequest(BaseModel):
    message: str
    channel: Optional[str] = "SMS"
    recipient: Optional[str] = None
    order_id: Optional[str] = None

class SendRequest(BaseModel):
    recipient: str = Field(..., min_length=1)
    subject: Optional[str] = "Nexus Notification"
    message: str = Field(..., min_length=1)
    channel: Optional[str] = "email"

NOTIFICATIONS_LOG: List[Dict[str, Any]] = []

@app.post("/notify")
def notify(request: NotifyRequest):
    notif_id = f"NOTIF-{uuid.uuid4().hex[:8].upper()}"
    entry = {
        "id": notif_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "channel": request.channel or "SMS",
        "recipient": request.recipient or "+91 98765 43210",
        "message": request.message,
        "status": "delivered"
    }
    NOTIFICATIONS_LOG.insert(0, entry)
    return {
        "status": "dispatched",
        "notification_id": notif_id,
        "notification_sent": request.message
    }

@app.post("/send")
def send(request: SendRequest):
    if not request.recipient or not request.recipient.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recipient cannot be empty."
        )
    notif_id = f"NOTIF-{uuid.uuid4().hex[:8].upper()}"
    entry = {
        "id": notif_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "channel": request.channel or "email",
        "recipient": request.recipient,
        "subject": request.subject,
        "message": request.message,
        "status": "delivered"
    }
    NOTIFICATIONS_LOG.insert(0, entry)
    return {"status": "success", "id": notif_id, "recipient": request.recipient}

@app.get("/notifications")
def get_notifications() -> List[Dict[str, Any]]:
    return NOTIFICATIONS_LOG[:50]