from collections.abc import Generator
from time import sleep

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from corebanking.config import get_core_banking_settings


class CoreBankingBase(DeclarativeBase):
    pass


def build_core_banking_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_core_banking_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


engine = build_core_banking_engine()
CoreBankingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_core_banking_db() -> Generator[Session, None, None]:
    with CoreBankingSessionLocal() as session:
        yield session


def create_core_banking_schema(target_engine: Engine = engine) -> None:
    from corebanking import models  # noqa: F401

    CoreBankingBase.metadata.create_all(target_engine)


def create_core_banking_schema_with_retry(
    target_engine: Engine = engine,
    *,
    attempts: int = 15,
    delay_seconds: float = 2,
) -> None:
    """Wait for an external database to accept connections during startup."""
    for attempt in range(1, attempts + 1):
        try:
            create_core_banking_schema(target_engine)
            return
        except OperationalError:
            if attempt == attempts:
                raise
            sleep(delay_seconds)
