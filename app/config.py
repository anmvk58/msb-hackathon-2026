from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "MSB Financial Radar"
    app_env: str = "development"
    agent_runtime: str = "local"
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
    llm_structured_retries: int = 2

    greennode_client_id: str | None = None
    greennode_client_secret: str | None = Field(default=None, repr=False)
    greennode_agent_identity: str | None = None
    greennode_endpoint_url: str | None = None
    run_greennode_integration_tests: bool = False

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> "Settings":
        if self.agent_runtime not in {"local", "greennode"}:
            raise ValueError("AGENT_RUNTIME must be 'local' or 'greennode'")
        if self.agent_runtime == "greennode":
            missing = [
                name
                for name, value in {
                    "GREENNODE_CLIENT_ID": self.greennode_client_id,
                    "GREENNODE_CLIENT_SECRET": self.greennode_client_secret,
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
            if self.llm_provider != "greennode":
                raise ValueError("AGENT_RUNTIME=greennode requires LLM_PROVIDER=greennode")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
