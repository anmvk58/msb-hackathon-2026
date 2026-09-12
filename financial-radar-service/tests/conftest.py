import os

os.environ["DATABASE_URL"] = "sqlite://"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.agent.local_runtime import LocalAgentRuntime
from app.tools import build_tool_registry
from tests.fakes import FakeBankingGateway


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session
    Base.metadata.drop_all(engine)


@pytest.fixture
def fake_banking_gateway() -> FakeBankingGateway:
    return FakeBankingGateway()


@pytest.fixture(autouse=True)
def inject_fake_banking_gateway(monkeypatch: pytest.MonkeyPatch, fake_banking_gateway: FakeBankingGateway):
    import app.agent.factory as factory_module
    import app.agent.local_runtime as runtime_module
    import app.main as main_module
    import app.tools.registry as registry_module

    monkeypatch.setattr(registry_module, "build_banking_gateway", lambda: fake_banking_gateway)
    monkeypatch.setattr(runtime_module, "build_tool_registry", lambda: build_tool_registry(fake_banking_gateway))
    monkeypatch.setattr(factory_module, "build_tool_registry", lambda: build_tool_registry(fake_banking_gateway))
    registry = build_tool_registry(fake_banking_gateway)
    monkeypatch.setattr(main_module, "registry", registry)
    monkeypatch.setattr(main_module, "runtime", LocalAgentRuntime(registry=registry))
