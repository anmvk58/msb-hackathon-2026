from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class CoreBankingSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CORE_BANKING_",
        extra="ignore",
    )

    database_url: str = "mysql+pymysql://corebanking:corebanking@localhost:3306/corebanking?charset=utf8mb4"
    seed_demo_on_start: bool = True
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_core_banking_settings() -> CoreBankingSettings:
    return CoreBankingSettings()
