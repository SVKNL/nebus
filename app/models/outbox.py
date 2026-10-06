"""ORM-модель транзакционного outbox.

Outbox pattern: событие пишется в ту же БД-транзакцию, что и агрегат.
Отдельный publisher читает неопубликованные строки и кладёт их в RabbitMQ.
Так мы не теряем событие, если брокер был недоступен в момент HTTP-ответа.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.payment import utc_now


class OutboxEvent(Base):
    """Неотправленное (или уже отправленное) доменное событие."""

    __tablename__ = "outbox"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    payment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("payments.id"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publish_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def mark_published(self, when: datetime) -> None:
        """Фиксируем успешную публикацию в брокер — строка больше не выбирается."""
        self.published_at = when

    def mark_failed(self, error: str) -> None:
        """Увеличиваем счётчик попыток publisher'а (это не DLQ consumer'а)."""
        self.publish_attempts += 1
        self.last_error = error[:2000]
