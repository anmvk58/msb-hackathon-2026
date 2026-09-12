from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "MSB Financial Sensing"
    app_env: str = "development"
    agent_runtime: str = "local"
    database_url: str = "postgresql+psycopg://financial_radar:financial_radar@localhost:5433/financial_radar"
    sql_echo: bool = False

    core_banking_base_url: str = "http://localhost:8090"
    core_banking_timeout_seconds: float = 10
    core_banking_api_key: str | None = Field(default=None, repr=False)
    cors_origins: str = "http://localhost:3000"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

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
    llm_structured_retries: int = 2
    agent_recommendation_ttl_seconds: int = 900
    scheduler_interval_seconds: int = 180
    scheduler_customer_ids: str = "C001,C002,C003,C004"

    @property
    def scheduler_customers(self) -> list[str]:
        return [item.strip() for item in self.scheduler_customer_ids.split(",") if item.strip()]

    greennode_client_id: str | None = None
    greennode_client_secret: str | None = Field(default=None, repr=False)
    greennode_agent_identity: str | None = None
    greennode_endpoint_url: str | None = None
    run_greennode_integration_tests: bool = False

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> "Settings":
        if self.agent_runtime not in {"local", "greennode"}:
            raise ValueError("AGENT_RUNTIME must be 'local' or 'greennode'")
        if self.llm_provider not in {None, "mock", "greennode"}:
            raise ValueError("LLM_PROVIDER must be 'mock' or 'greennode'")
        if self.llm_provider == "greennode":
            missing = [
                name
                for name, value in {
                    "LLM_BASE_URL": self.llm_base_url,
                    "LLM_MODEL": self.llm_model,
                    "LLM_API_KEY": self.llm_api_key,
                }.items()
                if not value
            ]
            if missing:
                raise ValueError(
                    "GreenNode runtime configuration is incomplete; missing: "
                    + ", ".join(missing)
                )
        if self.agent_runtime == "greennode" and self.llm_provider != "greennode":
            raise ValueError("AGENT_RUNTIME=greennode requires LLM_PROVIDER=greennode")
        if self.agent_recommendation_ttl_seconds <= 0:
            raise ValueError("AGENT_RECOMMENDATION_TTL_SECONDS must be greater than zero")
        if self.scheduler_interval_seconds <= 0:
            raise ValueError("SCHEDULER_INTERVAL_SECONDS must be greater than zero")
        if not self.scheduler_customers:
            raise ValueError("SCHEDULER_CUSTOMER_IDS must include at least one customer")
        if not self.core_banking_base_url.startswith(("http://", "https://")):
            raise ValueError("CORE_BANKING_BASE_URL must be an HTTP(S) URL")
        if self.core_banking_timeout_seconds <= 0:
            raise ValueError("CORE_BANKING_TIMEOUT_SECONDS must be greater than zero")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
