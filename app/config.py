from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "MSB Financial Radar"
    app_env: str = "development"
    database_url: str = "sqlite:///./financial_radar.db"
    sql_echo: bool = False

    spending_anomaly_threshold: float = 0.20
    spending_baseline_months: int = 3
    recurring_lookahead_days: int = 14
    cashflow_spending_lookback_days: int = 30
    cashflow_medium_ratio: float = 0.50
    shopping_budget_income_ratio: float = 0.16

    llm_provider: str | None = None
    llm_base_url: str | None = None
    llm_api_key: str | None = Field(default=None, repr=False)
    llm_model: str | None = None
    llm_timeout_seconds: int = 60

    greennode_base_url: str | None = None
    greennode_api_key: str | None = Field(default=None, repr=False)
    greennode_model: str | None = None
    greennode_agent_id: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
