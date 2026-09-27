from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from .telemetry import instrument_app

app = FastAPI(
    title="Users Service",
    description="Enterprise User Profiles, Addresses, and Wishlist Microservice",
    version="1.0.0"
)
instrument_app(app, "users-service")

@app.get("/healthz")
def healthz():
    return {"status": "healthy", "service": "users"}

class AddressModel(BaseModel):
    id: str
    label: str
    full_name: str
    phone: str
    street: str
    city: str
    state: str
    postal_code: str
    is_default: bool = False

class UserProfile(BaseModel):
    username: str
    email: str
    full_name: str
    phone: Optional[str] = None
    is_prime: bool = True
    member_since: str = "2024"
    loyalty_points: int = 1540
    addresses: List[Dict[str, Any]] = []
    wishlist: List[int] = []

PROFILES: Dict[str, Dict[str, Any]] = {
    "admin": {
        "username": "admin",
        "email": "admin@devopsnexus.io",
        "full_name": "DevOps Nexus Administrator",
        "phone": "+91 98888 12345",
        "is_prime": True,
        "member_since": "2023",
        "loyalty_points": 5000,
        "addresses": [
            {
                "id": "addr-1",
                "label": "Headquarters",
                "full_name": "DevOps Nexus Admin",
                "phone": "+91 98888 12345",
                "street": "100 Server Farm Way, Cloud City",
                "city": "Bangalore",
                "state": "Karnataka",
                "postal_code": "560100",
                "is_default": True
            }
        ],
        "wishlist": [1, 3, 4]
    },
    "customer": {
        "username": "customer",
        "email": "manikandan@amazon-shopper.io",
        "full_name": "Manikandan Srinivasan",
        "phone": "+91 98765 43210",
        "is_prime": True,
        "member_since": "2024",
        "loyalty_points": 2450,
        "addresses": [
            {
                "id": "addr-home",
                "label": "Home",
                "full_name": "Manikandan Srinivasan",
                "phone": "+91 98765 43210",
                "street": "Flat 402, Green Valley Apartments, Koramangala 4th Block",
                "city": "Bangalore",
                "state": "Karnataka",
                "postal_code": "560034",
                "is_default": True
            },
            {
                "id": "addr-work",
                "label": "Office",
                "full_name": "Manikandan Srinivasan",
                "phone": "+91 98765 43210",
                "street": "Tech Park, Building 3, Outer Ring Road",
                "city": "Bangalore",
                "state": "Karnataka",
                "postal_code": "560103",
                "is_default": False
            }
        ],
        "wishlist": [1, 2, 5, 8]
    }
}

@app.get("/users/{username}")
def get_user_profile(username: str):
    uname = username.lower().strip()
    if uname in PROFILES:
        return PROFILES[uname]
    raise HTTPException(status_code=404, detail="User not found")

@app.get("/users/{username}/wishlist")
def get_wishlist(username: str):
    uname = username.lower().strip()
    if uname in PROFILES:
        return {"wishlist": PROFILES[uname].get("wishlist", [])}
    raise HTTPException(status_code=404, detail="User not found")

@app.post("/users/{username}/wishlist")
def toggle_wishlist(username: str, product_id: int):
    uname = username.lower().strip()
    if uname not in PROFILES:
        PROFILES[uname] = {
            "username": uname,
            "email": f"{uname}@devopsnexus.io",
            "full_name": uname.capitalize(),
            "is_prime": True,
            "addresses": [],
            "wishlist": []
        }
    
    wish = PROFILES[uname]["wishlist"]
    if product_id in wish:
        wish.remove(product_id)
        action = "removed"
    else:
        wish.append(product_id)
        action = "added"
        
    return {"status": "success", "action": action, "wishlist": wish}