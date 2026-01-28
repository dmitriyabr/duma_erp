from typing import Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://erp_user:erp_password@localhost:5432/school_erp"

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # App
    app_env: str = "development"
    debug: bool = True
    # Can be a comma-separated string or list
    cors_allowed_origins: Union[str, list[str]] = "http://localhost:3000,http://localhost:5173"

    # File storage (attachments: payment confirmations, proofs). Dev: local folder; prod: S3/R2.
    storage_path: str = "uploads"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @field_validator("database_url", mode="before")
    @classmethod
    def convert_database_url(cls, v):
        """Convert postgres:// or postgresql:// to postgresql+asyncpg:// for Railway/Heroku."""
        if not v:
            raise ValueError("DATABASE_URL is required")
        if isinstance(v, str):
            # Railway can provide either postgres:// or postgresql://
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://"):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


settings = Settings()
