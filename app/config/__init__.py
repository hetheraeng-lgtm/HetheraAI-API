import os
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"


class AppSettings(BaseSettings):
    """Application settings loaded from environment variables with production-ready defaults."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    # JWT Authentication
    ACCESS_TOKEN_EXPIRES: int = Field(
        3600, description="JWT token expiration time in seconds"
    )
    ALGORITHM: str = Field("HS256", description="JWT algorithm")
    SECRET_KEY: str = Field(..., description="Secret key for JWT encoding/decoding")
    RESET_TOKEN_EXPIRY_HOURS: float = Field(..., description="Reset token expiry hours")

    # CORS settings
    ALLOWED_ORIGINS: List[str] = Field(
        ["http://localhost:3000", "http://localhost:8000"],
        description="List of allowed origins for CORS",
    )
    ALLOW_CREDENTIALS: bool = Field(True, description="Allow credentials for CORS")
    ALLOW_METHODS: List[str] = Field(["*"], description="Allowed HTTP methods for CORS")
    ALLOW_HEADERS: List[str] = Field(["*"], description="Allowed HTTP headers for CORS")

    # API settings
    API_VERSION: str = Field("/api/v1", description="API version prefix")
    APP_NAME: str = Field("HetheraAI-api", description="Application name")
    SWAGGER_DOCS_URL: str = Field("/docs", description="Swagger documentation URL")

    # Database settings
    DATABASE_SCHEMA: str = Field("public", description="Database schema")
    SQLALCHEMY_DATABASE_URL: str = Field(
        ..., description="Sync database URL (used by Alembic)"
    )
    ASYNC_DATABASE_URL: str = Field(
        ..., description="Async database URL (used by SQLAlchemy engine)"
    )

    # VTPass settings
    VTPASS_API_KEY: str = Field(..., description="VTPass API key")
    VTPASS_SECRET_KEY: str = Field(..., description="VTPass secret key")
    VTPASS_PUBLIC_KEY: str = Field(..., description="VTPass public key")
    VTPASS_BASE_URL: str = Field(..., description="VTPass base URL")

    # Paystack settings
    PAYSTACK_SECRET_KEY: str = Field(..., description="Paystack secret key")
    PAYSTACK_PUBLIC_KEY: str = Field("", description="Paystack public key")
    PAYSTACK_BASE_URL: str = Field(
        "https://api.paystack.co", description="Paystack base URL"
    )
    PAYSTACK_MERCHANT_EMAIL: str = Field(
        ..., description="Merchant email for Paystack charges"
    )
    PAYSTACK_CALLBACK_URL: str = Field(
        "https://hethera.ai/payment-callback",
        description="Redirect URL after card authorization",
    )

    # Redis settings
    REDIS_URI: str = Field(..., description="Redis connection URI")

    # Environment
    ENVIRONMENT: str = Field(
        "development", description="Environment (development, staging, production)"
    )
    DEBUG: bool = Field(not IS_PRODUCTION, description="Debug mode")


@lru_cache()
def get_settings() -> AppSettings:
    """Get cached settings to avoid loading .env file multiple times."""
    return AppSettings()  # type: ignore[call-arg]


app_settings = get_settings()
