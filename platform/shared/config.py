# --- Shared Platform Configurations Parser ---
from pydantic_settings import BaseSettings, SettingsConfigDict

class PlatformSettings(BaseSettings):
    # API Backend Server
    PORT: int = 8000
    LOG_LEVEL: str = "info"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:5173"
    JWT_SECRET_KEY: str = "devops-nexus-super-secure-jwt-key-2026-production"
    
    # Observability Stack
    PROMETHEUS_URL: str = "http://prometheus-service.devops-nexus.svc.cluster.local:9090"
    LOKI_URL: str = "http://loki-service.devops-nexus.svc.cluster.local:3100"
    
    # GitOps / ArgoCD
    ARGOCD_SERVER: str = "argocd-server.argocd.svc.cluster.local"
    ARGOCD_TOKEN: str = ""
    
    # AI Engine Settings
    AI_PROVIDER: str = "ollama"
    OLLAMA_HOST: str = "http://localhost:11434"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    GROQ_API_KEY: str = ""
    LMSTUDIO_HOST: str = "http://localhost:1234/v1"
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    
    # Caching
    REDIS_URL: str = "redis://localhost:6379/0"

    # AWS Account Defaults (Persistent Connection)
    DEFAULT_AWS_ACCOUNT_ID: str = "605294565283"
    DEFAULT_AWS_ROLE_ARN: str = "arn:aws:iam::605294565283:role/DevOpsNexusAccessRole"
    DEFAULT_AWS_REGION: str = "ap-south-1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate settings singleton
settings = PlatformSettings()
