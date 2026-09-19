from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADMIN_", env_file=".env", extra="ignore")

    core_banking_base_url: str = "http://localhost:8090"
    core_banking_timeout_seconds: float = 10.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
