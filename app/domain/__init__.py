"""Домен: статусы, валюты, ошибки. Без FastAPI, SQLAlchemy и брокера."""

from app.domain.enums import Currency, PaymentStatus
from app.domain.errors import (
    IdempotencyConflictError,
    NonRetryableError,
    PaymentError,
    PaymentNotFoundError,
    PaymentProcessingError,
)

__all__ = [
    "Currency",
    "IdempotencyConflictError",
    "NonRetryableError",
    "PaymentError",
    "PaymentNotFoundError",
    "PaymentProcessingError",
    "PaymentStatus",
]
