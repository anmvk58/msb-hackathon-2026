from typing import TypeVar
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from corebanking.models import IdempotencyRecord


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


def replay(
    session: Session,
    *,
    operation: str,
    key: str | None,
    response_model: type[ResponseModel],
) -> ResponseModel | None:
    if not key:
        return None
    record = session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.idempotency_key == key,
        )
    )
    return response_model.model_validate(record.response_data) if record else None


def remember(
    session: Session,
    *,
    operation: str,
    key: str | None,
    response: BaseModel,
) -> None:
    if not key:
        return
    session.add(
        IdempotencyRecord(
            record_id=f"IDEM-{uuid4().hex[:12].upper()}",
            operation=operation,
            idempotency_key=key,
            response_data=jsonable_encoder(response),
        )
    )
