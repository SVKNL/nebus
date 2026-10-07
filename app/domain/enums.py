"""Доменные перечисления платежа. Не зависят от ORM и HTTP."""

from enum import StrEnum


class PaymentStatus(StrEnum):
    """Жизненный цикл платежа."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Currency(StrEnum):
    """Валюты, которые принимает сервис."""

    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"
