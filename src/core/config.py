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
    # S3/R2 (Cloudflare R2). If set, attachments are stored in bucket instead of local folder.
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_bucket: str | None = None
    s3_region: str = "auto"

    # School & payment details (for PDF: invoices, receipts). Set in .env — one block.
    school_name: str = "Your School Name"
    school_address: str = ""
    school_phone: str = ""
    school_email: str = ""
    mpesa_business_number: str = ""
    bank_name: str = ""
    bank_account_name: str = ""
    bank_account_number: str = ""
    bank_branch: str = ""
    bank_swift_code: str = ""

    @property
    def school_info(self) -> dict[str, str]:
        """One dict for PDF templates: school name, address, phone, email."""
        return {
            "name": self.school_name,
            "address": self.school_address,
            "phone": self.school_phone,
            "email": self.school_email,
        }

    @property
    def bank_info(self) -> dict[str, str]:
        """One dict for PDF invoice: bank details."""
        return {
            "bank_name": self.bank_name,
            "account_name": self.bank_account_name,
            "account_number": self.bank_account_number,
            "branch": self.bank_branch,
            "swift_code": self.bank_swift_code,
        }

    @property
    def use_s3(self) -> bool:
        """True when S3/R2 is configured (prod)."""
        return bool(self.s3_bucket and self.s3_endpoint_url and self.s3_access_key and self.s3_secret_key)

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
