"""
Core configuration for PAI Server.
Loads settings from environment variables.
"""
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Pepper"
    APP_VERSION: str = "1.0"
    DEBUG: bool = False

    # API
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql://pai:pai@localhost:5432/pai"

    # Security
    SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30 minuten (kort voor veiligheid)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 dagen

    # CORS
    ALLOWED_ORIGINS: list[str] = ["*"]

    # OAuth - Google
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # OAuth - Microsoft
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    MICROSOFT_TENANT_ID: str = "common"  # common for multi-tenant, or specific tenant ID

    # External APIs
    ANTHROPIC_API_KEY: Optional[str] = None  # For Claude AI integration (later)

    # Email (SendGrid)
    SENDGRID_API_KEY: Optional[str] = None

    # Frontend URL for verification links
    FRONTEND_URL: str = "http://localhost:5174"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
