"""Unauthenticated administrative CRUD API for synthetic demo data only."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from corebanking.database import get_core_banking_db
from corebanking.models import (
    Account, Budget, CreditCard, Customer, IdempotencyRecord, MSinhLoiAccount, OverdraftFacility,
    PreapprovedLoanOffer, RecurringEvent, Reminder, SavingGoal, TermDeposit,
    Transaction,
)


router = APIRouter(prefix="/api/admin", tags=["Admin CRUD"])


RESOURCE_MODELS = {
    "accounts": Account,
    "transactions": Transaction,
    "recurring-events": RecurringEvent,
    "budgets": Budget,
    "goals": SavingGoal,
    "reminders": Reminder,
    "overdraft-facilities": OverdraftFacility,
    "term-deposits": TermDeposit,
    "m-sinh-loi-accounts": MSinhLoiAccount,
    "credit-cards": CreditCard,
    "loan-offers": PreapprovedLoanOffer,
}

ID_PREFIXES = {
    "accounts": "A", "transactions": "TX", "recurring-events": "R",
    "budgets": "B", "goals": "G", "reminders": "RM",
    "overdraft-facilities": "OD", "term-deposits": "TD",
    "credit-cards": "CC", "loan-offers": "LO", "m-sinh-loi-accounts": "MSL",
}


def _serialize(instance: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for column in inspect(instance).mapper.column_attrs:
        value = getattr(instance, column.key)
        result[column.key] = value.value if isinstance(value, Enum) else value
    return result


def _model_info(model: type) -> tuple[str, set[str], set[str]]:
    mapper = inspect(model)
    primary_key = mapper.primary_key[0].key
    fields = {column.key for column in mapper.columns}
    required = {
        column.key for column in mapper.columns
        if not column.nullable and column.default is None and column.server_default is None
        and not column.primary_key and column.key != "customer_id"
    }
    return primary_key, fields, required


def _coerce(model: type, field: str, value: Any) -> Any:
    if value is None:
        return None
    column = inspect(model).columns[field]
    try:
        python_type = column.type.python_type
    except (AttributeError, NotImplementedError):
        return value
    try:
        if isinstance(python_type, type) and issubclass(python_type, Enum):
            return python_type(value)
        if python_type is Decimal:
            return Decimal(str(value))
        if python_type is datetime and isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        if python_type is date and isinstance(value, str):
            return date.fromisoformat(value)
        if python_type is bool and isinstance(value, str):
            return value.lower() in {"true", "1", "yes"}
        return value if isinstance(value, python_type) else python_type(value)
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid value for {field}: {value}") from exc


def _apply_payload(instance: Any, model: type, payload: dict[str, Any], *, create: bool) -> None:
    primary_key, fields, required = _model_info(model)
    protected = {primary_key, "customer_id"}
    unknown = set(payload) - fields
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown fields: {', '.join(sorted(unknown))}")
    if not create and protected.intersection(payload):
        raise HTTPException(status_code=422, detail="Identifiers and customer_id cannot be changed")
    if create:
        missing = required - set(payload)
        if missing:
            raise HTTPException(status_code=422, detail=f"Missing fields: {', '.join(sorted(missing))}")
    for field, value in payload.items():
        setattr(instance, field, _coerce(model, field, value))


def _customer(session: Session, customer_id: str) -> Customer:
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


def _resource(resource: str) -> type:
    model = RESOURCE_MODELS.get(resource)
    if model is None:
        raise HTTPException(status_code=404, detail="Unknown customer resource")
    return model


def _item(session: Session, model: type, customer_id: str, item_id: str) -> Any:
    item = session.get(model, item_id)
    if item is None or item.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Resource item not found for customer")
    return item


def _validate_m_sinh_loi(session: Session, item: MSinhLoiAccount) -> None:
    payment = session.get(Account, item.payment_account_id)
    if payment is None or payment.customer_id != item.customer_id or payment.account_type != "PAYMENT":
        raise HTTPException(status_code=422, detail="payment_account_id must be a payment account of this customer")
    if item.minimum_payment_balance is None or item.minimum_payment_balance < Decimal("1000000"):
        raise HTTPException(status_code=422, detail="minimum_payment_balance must be at least 1000000")
    if item.balance is not None and item.balance < 0:
        raise HTTPException(status_code=422, detail="balance cannot be negative")
    if item.sweep_hour is not None and not 0 <= item.sweep_hour <= 23:
        raise HTTPException(status_code=422, detail="sweep_hour must be between 0 and 23")
    if item.status is not None and item.status not in {"ACTIVE", "INACTIVE"}:
        raise HTTPException(status_code=422, detail="status must be ACTIVE or INACTIVE")


@router.get("/metadata")
def metadata() -> dict[str, Any]:
    resources: dict[str, Any] = {}
    for name, model in RESOURCE_MODELS.items():
        primary_key, _, required = _model_info(model)
        resources[name] = {
            "id_field": primary_key,
            "required_fields": sorted(required),
            "fields": [column.key for column in inspect(model).columns],
        }
    return {"authentication": False, "resources": resources}


@router.get("/customers")
def list_customers(session: Session = Depends(get_core_banking_db)) -> list[dict[str, Any]]:
    return [_serialize(item) for item in session.scalars(select(Customer).order_by(Customer.customer_id)).all()]


@router.post("/customers", status_code=status.HTTP_201_CREATED)
def create_customer(payload: dict[str, Any], session: Session = Depends(get_core_banking_db)) -> dict[str, Any]:
    customer_id = str(payload.get("customer_id", "")).strip()
    if not customer_id:
        raise HTTPException(status_code=422, detail="customer_id is required")
    if session.get(Customer, customer_id):
        raise HTTPException(status_code=409, detail="Customer already exists")
    customer = Customer(customer_id=customer_id)
    _apply_payload(customer, Customer, payload, create=True)
    session.add(customer)
    session.commit()
    session.refresh(customer)
    return _serialize(customer)


@router.get("/customers/{customer_id}")
def get_customer(customer_id: str, session: Session = Depends(get_core_banking_db)) -> dict[str, Any]:
    return _serialize(_customer(session, customer_id))


@router.patch("/customers/{customer_id}")
def update_customer(customer_id: str, payload: dict[str, Any], session: Session = Depends(get_core_banking_db)) -> dict[str, Any]:
    customer = _customer(session, customer_id)
    _apply_payload(customer, Customer, payload, create=False)
    session.commit()
    session.refresh(customer)
    return _serialize(customer)


@router.delete("/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(customer_id: str, session: Session = Depends(get_core_banking_db)) -> Response:
    customer = _customer(session, customer_id)
    # Explicit ordering keeps the operation portable between SQLite tests and MySQL.
    for model in (Transaction, Budget, RecurringEvent, SavingGoal, Reminder,
                  OverdraftFacility, TermDeposit, MSinhLoiAccount, CreditCard, PreapprovedLoanOffer, Account):
        session.execute(delete(model).where(model.customer_id == customer_id))
    session.execute(delete(IdempotencyRecord).where(IdempotencyRecord.operation.contains(customer_id)))
    session.delete(customer)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/customers/{customer_id}/overview")
def customer_overview(customer_id: str, session: Session = Depends(get_core_banking_db)) -> dict[str, Any]:
    result: dict[str, Any] = {"customer": _serialize(_customer(session, customer_id))}
    for name, model in RESOURCE_MODELS.items():
        result[name] = [_serialize(item) for item in session.scalars(
            select(model).where(model.customer_id == customer_id)
        ).all()]
    return result


@router.get("/customers/{customer_id}/{resource}")
def list_resource(customer_id: str, resource: str, session: Session = Depends(get_core_banking_db)) -> list[dict[str, Any]]:
    _customer(session, customer_id)
    model = _resource(resource)
    return [_serialize(item) for item in session.scalars(select(model).where(model.customer_id == customer_id)).all()]


@router.post("/customers/{customer_id}/{resource}", status_code=status.HTTP_201_CREATED)
def create_resource(customer_id: str, resource: str, payload: dict[str, Any], session: Session = Depends(get_core_banking_db)) -> dict[str, Any]:
    _customer(session, customer_id)
    model = _resource(resource)
    primary_key, _, _ = _model_info(model)
    item_id = str(payload.get(primary_key) or f"{ID_PREFIXES[resource]}-{uuid4().hex[:12].upper()}")
    if session.get(model, item_id):
        raise HTTPException(status_code=409, detail="Resource item already exists")
    if model is MSinhLoiAccount and session.scalar(select(MSinhLoiAccount).where(MSinhLoiAccount.customer_id == customer_id)):
        raise HTTPException(status_code=409, detail="Customer already has an M-Sinh lời account")
    item = model(**{primary_key: item_id, "customer_id": customer_id})
    clean_payload = {key: value for key, value in payload.items() if key not in {primary_key, "customer_id"}}
    _apply_payload(item, model, clean_payload, create=True)
    if model is MSinhLoiAccount:
        _validate_m_sinh_loi(session, item)
    session.add(item)
    session.commit()
    session.refresh(item)
    return _serialize(item)


@router.get("/customers/{customer_id}/{resource}/{item_id}")
def get_resource(customer_id: str, resource: str, item_id: str, session: Session = Depends(get_core_banking_db)) -> dict[str, Any]:
    return _serialize(_item(session, _resource(resource), customer_id, item_id))


@router.patch("/customers/{customer_id}/{resource}/{item_id}")
def update_resource(customer_id: str, resource: str, item_id: str, payload: dict[str, Any], session: Session = Depends(get_core_banking_db)) -> dict[str, Any]:
    model = _resource(resource)
    item = _item(session, model, customer_id, item_id)
    _apply_payload(item, model, payload, create=False)
    if model is MSinhLoiAccount:
        _validate_m_sinh_loi(session, item)
    session.commit()
    session.refresh(item)
    return _serialize(item)


@router.delete("/customers/{customer_id}/{resource}/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resource(customer_id: str, resource: str, item_id: str, session: Session = Depends(get_core_banking_db)) -> Response:
    item = _item(session, _resource(resource), customer_id, item_id)
    session.delete(item)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
