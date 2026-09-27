from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import uuid
import datetime
from .telemetry import instrument_app

app = FastAPI(
    title="Auth Service",
    description="Enterprise Authentication & Token Issuing Microservice",
    version="1.0.0"
)
instrument_app(app, "auth-service")

@app.get("/healthz")
def healthz():
    return {"status": "healthy", "service": "auth"}

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=4)
    email: str = Field(...)
    full_name: str = Field(...)

USERS_DB = {
    "admin": {
        "password": "password",
        "role": "administrator",
        "email": "admin@devopsnexus.io",
        "full_name": "Nexus System Administrator",
        "is_prime": True
    },
    "customer": {
        "password": "customer123",
        "role": "customer",
        "email": "manikandan@amazon-shopper.io",
        "full_name": "Manikandan Srinivasan",
        "is_prime": True
    },
    "guest": {
        "password": "guest",
        "role": "guest",
        "email": "guest@devopsnexus.io",
        "full_name": "Guest Shopper",
        "is_prime": False
    }
}

ACTIVE_TOKENS: Dict[str, Dict[str, Any]] = {
    "mock-jwt-token-xyz": {"username": "admin", "role": "administrator", "is_prime": True}
}

@app.post("/login")
def login(request: LoginRequest):
    uname = request.username.strip().lower()
    user = USERS_DB.get(uname)
    
    if user and user["password"] == request.password:
        token = f"nexus-jwt-{uname}-{uuid.uuid4().hex[:12]}"
        ACTIVE_TOKENS[token] = {
            "username": uname,
            "role": user["role"],
            "full_name": user["full_name"],
            "email": user["email"],
            "is_prime": user.get("is_prime", False)
        }
        return {
            "access_token": token,
            "token_type": "bearer",
            "username": uname,
            "full_name": user["full_name"],
            "role": user["role"],
            "email": user["email"],
            "is_prime": user.get("is_prime", False)
        }
    
    # Check legacy test admin credentials
    if uname == "admin" and request.password == "password":
        return {"access_token": "mock-jwt-token-xyz", "token_type": "bearer"}
        
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, 
        detail="Incorrect username or password"
    )

@app.post("/register")
def register(request: RegisterRequest):
    uname = request.username.strip().lower()
    if uname in USERS_DB:
        raise HTTPException(status_code=400, detail="Username already exists.")
        
    USERS_DB[uname] = {
        "password": request.password,
        "role": "customer",
        "email": request.email,
        "full_name": request.full_name,
        "is_prime": True
    }
    
    token = f"nexus-jwt-{uname}-{uuid.uuid4().hex[:12]}"
    ACTIVE_TOKENS[token] = {
        "username": uname,
        "role": "customer",
        "full_name": request.full_name,
        "email": request.email,
        "is_prime": True
    }
    
    return {
        "access_token": token,
        "username": uname,
        "full_name": request.full_name,
        "message": "User registered and logged in successfully."
    }

@app.post("/verify")
def verify_token(token: str):
    if token in ACTIVE_TOKENS:
        info = ACTIVE_TOKENS[token]
        return {
            "active": True,
            "username": info["username"],
            "role": info["role"],
            "full_name": info.get("full_name"),
            "is_prime": info.get("is_prime", False)
        }
    if token == "mock-jwt-token-xyz":
        return {"active": True, "username": "admin", "role": "administrator"}
    return {"active": False}