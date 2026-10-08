# --- DevOps Nexus Core Platform API Backend ---
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError

# pyrefly: ignore [missing-import]
from app.core.settings import settings
from app.core.logging import setup_logging, RequestLoggingMiddleware
from app.middleware import RequestIDMiddleware, ProcessingTimeMiddleware, GlobalExceptionMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import root_router, health_router, version_router, auth_router
from app.routers.k8s import router as k8s_router
from app.routers.monitoring import router as monitoring_router
from app.routers.gitops import router as gitops_router
from app.routers.ai import router as ai_router

# Setup logger configurations on startup
setup_logging()


# Initialize FastAPI application
app = FastAPI(
    title="Microservice Deployment & Monitoring Platform",
    description="Unified DevOps Nexus Core REST API Engine.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

@app.on_event("startup")
async def startup_event():
    try:
        from app.services.platform_initializer import platform_initializer
        platform_initializer.initialize_platform()
    except Exception as e:
        setup_logging().warning(f"Platform initializer failed on startup: {str(e)}")

    try:
        from app.services.cluster_state_cache import cluster_state_cache
        cluster_state_cache.start_background_daemon()
    except Exception as e:
        setup_logging().warning(f"Failed to start ClusterStateCache daemon: {str(e)}")

# Exception handlers for request/response validation and uniform error formats
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": "AUTHENTICATION_FAILED" if exc.status_code == 401 else "FORBIDDEN" if exc.status_code == 403 else "BAD_REQUEST",
                "message": exc.detail
            },
            "request_id": getattr(request.state, "request_id", None)
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed.",
                "details": exc.errors()
            },
            "request_id": getattr(request.state, "request_id", None)
        }
    )

# 1. Add custom security headers middleware (Part 4)
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# 2. Register Custom Platform Middlewares (Execution runs bottom-to-top)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ProcessingTimeMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(GlobalExceptionMiddleware)

# 3. CORS Middlewares Setup (Registered last to ensure outermost execution on responses)
allowed_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers.admin import router as admin_router
from app.routers.clusters import router as clusters_router
from app.routers.agent import router as agent_router
from app.routers.aws import router as aws_router

# 4. Mount Endpoint Routers
app.include_router(root_router, tags=["Root"])
app.include_router(health_router, tags=["Probes"])
app.include_router(version_router, tags=["Version"])
app.include_router(auth_router, tags=["Authentication"])
app.include_router(k8s_router, tags=["Kubernetes"])
app.include_router(monitoring_router, tags=["Observability"])
app.include_router(gitops_router, tags=["GitOps"])
app.include_router(ai_router, tags=["AI Assistant"])
app.include_router(admin_router, tags=["Administration"])
app.include_router(clusters_router, tags=["Cluster Management"])
app.include_router(agent_router, tags=["Autonomous Agent"])
app.include_router(aws_router, tags=["AWS & Amazon EKS"])


