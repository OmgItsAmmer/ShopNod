"""Environment-driven settings shared by api, mcp and worker."""
from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT = "dev-only-jwt-signing-key-change-me-0123456789"
_DEV_MCP = "dev-only-mcp-agent-token-secret-change-me-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite+aiosqlite:///./shopnod.db"
    REDIS_URL: str = ""
    APP_ENV: str = "local"
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: str = ""

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_AGENT: str = "gpt-4o"
    OPENAI_MODEL_FAST: str = "gpt-4o-mini"

    JWT_SIGNING_KEY: str = _DEV_JWT
    QR_SIGNING_KEY: str = ""  # Ed25519 private key, base64 (raw 32 bytes); dev key derived if empty

    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:admin@shopnod.local"
    EXPO_ACCESS_TOKEN: str = ""  # unused since the shopper app moved to Flutter; kept so old .env files still load
    FIREBASE_CREDENTIALS: str = ""  # service-account JSON, base64 (FCM push to the Flutter app)
    # Simulated shoppers (Plan 3 Phase 2): delay before a simulated claim is redeemed, and claim likelihood
    SIM_REDEEM_MIN_S: float = 30.0
    SIM_REDEEM_MAX_S: float = 120.0
    SIM_SHOPPERS: int = 40
    SIM_BURST_SPAN_S: float = 20.0  # "burst" spreads 5 redemptions over this many seconds

    # Prediction context (weather for the shopper's area; Open-Meteo is free and needs no key)
    WEATHER_ENABLED: bool = True
    WEATHER_URL: str = "https://api.open-meteo.com/v1/forecast"
    WEATHER_TIMEOUT_S: float = 2.0

    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_METER_EVENT_NAME: str = "shopnod_redemption"
    STRIPE_PRO_PRICE_ID: str = ""
    STRIPE_METERED_PRICE_ID: str = ""

    EMAIL_PROVIDER_KEY: str = ""
    SHOP_WEB_URL: str = "http://localhost:3000"
    SHOPPER_WEB_URL: str = "http://localhost:3000/shopper"  # the shopper view lives in the same web app
    API_PUBLIC_URL: str = "http://localhost:8000"
    MCP_PUBLIC_URL: str = "http://localhost:8001"
    DEMO_MODE: bool = True
    CORS_ORIGINS: str = "http://localhost:3000"
    MCP_AGENT_TOKEN_SECRET: str = _DEV_MCP
    MCP_INTERNAL_URL: str = "http://localhost:8001/mcp"

    # Tunables
    PROPOSAL_LEAD_MINUTES: int = 10
    SESSION_TTL_HOURS: int = 24 * 7
    AGENT_TIMEOUT_S: float = 8.0
    COPY_TIMEOUT_S: float = 5.0
    DEMO_LOGIN_PER_MINUTE: int = 30
    REDEMPTION_FEE_MINOR: int = 1000  # approx. fee per redemption in shop currency, for the ROI estimate
    REDEMPTION_FEE_USD_CENTS: int = 10  # shown on the billing page (Stripe test mode)

    @field_validator("DATABASE_URL")
    @classmethod
    def _async_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return "postgresql+asyncpg://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == "prod"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_prod and (s.JWT_SIGNING_KEY == _DEV_JWT or s.MCP_AGENT_TOKEN_SECRET == _DEV_MCP):
        raise RuntimeError("JWT_SIGNING_KEY and MCP_AGENT_TOKEN_SECRET must be set in prod")
    return s


def reset_settings_cache() -> None:
    get_settings.cache_clear()
