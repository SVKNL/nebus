"""ORM-модель платежа."""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Numeric, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _enum_values(enum: type) -> list[str]:
    """В PostgreSQL храним value enum (pending), а не имя (PENDING)."""
    return [item.value for item in enum]


def utc_now() -> datetime:
    """TZ-aware UTC для Python-side default (чтобы created_at был в объекте до refresh)."""
    return datetime.now(UTC)


class PaymentStatus(StrEnum):
    """Жизненный цикл платежа согласно ТЗ."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Currency(StrEnum):
    """Поддерживаемые валюты (ISO-подобные коды из задания)."""

    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class Payment(Base):
    """Платёж, принятый API и обработанный consumer'ом через эмуляцию шлюза.

    Идемпотентность обеспечивается уникальным `idempotency_key`: повторный
    POST с тем же ключом не создаёт вторую запись.
    """

    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_payments_amount_positive"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[Currency] = mapped_column(
        SAEnum(
            Currency,
            name="payment_currency",
            native_enum=True,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Имя атрибута extra_metadata: у DeclarativeBase уже есть metadata.
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(
            PaymentStatus,
            name="payment_status",
            native_enum=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=PaymentStatus.PENDING,
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    webhook_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    webhook_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def is_terminal(self) -> bool:
        """Терминальные статусы больше не меняются шлюзом (идемпотентный consumer)."""
        return self.status in {PaymentStatus.SUCCEEDED, PaymentStatus.FAILED}
