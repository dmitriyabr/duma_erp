import os
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
    cors_allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Railway/Heroku provide DATABASE_URL as postgres://, convert to postgresql+asyncpg://
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql+asyncpg://", 1)

        # Parse CORS_ALLOWED_ORIGINS from comma-separated string if it's an env var
        cors_env = os.getenv("CORS_ALLOWED_ORIGINS")
        if cors_env:
            self.cors_allowed_origins = [origin.strip() for origin in cors_env.split(",")]


settings = Settings()
