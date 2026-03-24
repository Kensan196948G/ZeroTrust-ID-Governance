"""
アプリケーション設定管理
pydantic-settings で環境変数から型安全に読み込み
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- アプリケーション ---
    APP_VERSION: str = "1.0.0"
    APP_ENV: Literal["development", "test", "production"] = "development"
    APP_SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1"]
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    # --- データベース ---
    DATABASE_URL: str = "postgresql://admin:password@localhost:5432/zerotrust_id"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- JWT ---
    JWT_SECRET_KEY: str = "jwt-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Azure / Entra ID ---
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""
    AZURE_CLIENT_SECRET: str = ""

    # --- Active Directory ---
    AD_SERVER: str = "ldaps://dc01.mirai.local"
    AD_BIND_DN: str = ""
    AD_BIND_PASSWORD: str = ""
    AD_BASE_DN: str = "DC=mirai,DC=local"

    # --- HENGEONE ---
    HENGEONE_SCIM_BASE_URL: str = "https://api.hengeone.com/scim/v2"
    HENGEONE_API_TOKEN: str = ""
    HENGEONE_TENANT_ID: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
