"""Контракт сообщения в очереди payments.new."""

from typing import Self
from uuid import UUID

from pydantic import BaseModel


class PaymentNewEvent(BaseModel):
    """Consumer'у достаточно идентификатора: остальное он читает из БД."""

    payment_id: UUID
    event_type: str = "payments.new"

    @classmethod
    def from_payment_id(cls, payment_id: UUID) -> Self:
        """Payload для строки outbox."""
        return cls(payment_id=payment_id)
