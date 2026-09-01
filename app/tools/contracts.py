from enum import StrEnum
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel
from sqlalchemy.orm import Session


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ConfirmationPolicy(StrEnum):
    NONE = "NONE"
    REQUIRED = "REQUIRED"
    EXPLICIT = "EXPLICIT"
    AUTHENTICATED = "AUTHENTICATED"


class ToolMetadata(BaseModel):
    name: str
    description: str
    risk_level: RiskLevel
    confirmation_policy: ConfirmationPolicy
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class BusinessTool(Protocol[InputT, OutputT]):
    name: str
    description: str
    risk_level: RiskLevel
    confirmation_policy: ConfirmationPolicy
    input_model: type[InputT]
    output_model: type[OutputT]

    def execute(self, session: Session, arguments: InputT) -> OutputT: ...


class ToolExecutionError(RuntimeError):
    pass

