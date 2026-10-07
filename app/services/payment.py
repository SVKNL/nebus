"""Прикладной слой платежей: создание, чтение, идемпотентность, outbox."""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import OUTBOX_EVENT_PAYMENTS_NEW
from app.domain.enums import Currency, PaymentStatus
from app.domain.errors import IdempotencyConflictError, PaymentNotFoundError
from app.models.outbox import OutboxEvent
from app.models.payment import Payment
from app.schemas.events import PaymentNewEvent
from app.schemas.http import PaymentCreateRequest

logger = logging.getLogger(__name__)


class PaymentService:
    """Оркестрация записи платежа и события outbox в одной транзакции."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        payload: PaymentCreateRequest,
        idempotency_key: str,
    ) -> tuple[Payment, bool]:
        """Создаёт платёж либо возвращает ранее созданный (replay).

        Возвращает (payment, is_replay). Replay — повтор с тем же ключом и тем же телом:
        клиент должен получить тот же 202, без второй публикации в очередь.

        Если ключ уже занят другим телом — IdempotencyConflictError (HTTP 409).
        Гонку двух параллельных POST ловим по UniqueViolation и повторяем чтение.
        """
        existing = await self._get_by_idempotency_key(idempotency_key)
        if existing is not None:
            self._assert_same_payload(existing, payload)
            return existing, True

        payment_id = uuid4()
        payment = Payment(
            id=payment_id,
            amount=payload.amount,
            currency=payload.currency,
            description=payload.description,
            extra_metadata=payload.metadata,
            status=PaymentStatus.PENDING,
            idempotency_key=idempotency_key,
            webhook_url=str(payload.webhook_url),
        )
        event = OutboxEvent(
            payment_id=payment_id,
            event_type=OUTBOX_EVENT_PAYMENTS_NEW,
            payload=PaymentNewEvent.from_payment_id(payment_id).model_dump(mode="json"),
        )
        # Сначала платёж, потом outbox: FK проверяется сразу, не в конце транзакции.
        self._session.add(payment)
        await self._session.flush()
        self._session.add(event)

        try:
            await self._session.commit()
        except IntegrityError:
            # Параллельный запрос с тем же ключом успел вставить строку раньше.
            await self._session.rollback()
            existing = await self._get_by_idempotency_key(idempotency_key)
            if existing is None:
                raise
            self._assert_same_payload(existing, payload)
            logger.info("Idempotent replay after race payment_id=%s", existing.id)
            return existing, True

        logger.info("Payment created payment_id=%s", payment.id)
        return payment, False

    async def get(self, payment_id: UUID) -> Payment:
        """Возвращает платёж или PaymentNotFoundError."""
        payment = await self._session.get(Payment, payment_id)
        if payment is None:
            raise PaymentNotFoundError
        return payment

    async def _get_by_idempotency_key(self, key: str) -> Payment | None:
        stmt = select(Payment).where(Payment.idempotency_key == key)
        return await self._session.scalar(stmt)

    @staticmethod
    def _assert_same_payload(existing: Payment, payload: PaymentCreateRequest) -> None:
        """Сравниваем каноническое представление, чтобы «тот же запрос» был строгим."""
        if not payloads_equivalent(existing, payload):
            raise IdempotencyConflictError(str(existing.id))


def payloads_equivalent(existing: Payment, payload: PaymentCreateRequest) -> bool:
    """Два запроса считаются одним платежом, если совпадают бизнес-поля.

    URL приводим к str: Pydantic Url и строка из БД иначе не сравнятся.
    Decimal сравниваем как Decimal, без float.
    """
    same_amount = Decimal(existing.amount) == payload.amount
    same_currency = existing.currency == Currency(payload.currency)
    same_description = existing.description == payload.description
    same_metadata = existing.extra_metadata == payload.metadata
    same_webhook = existing.webhook_url.rstrip("/") == str(payload.webhook_url).rstrip("/")
    return all((same_amount, same_currency, same_description, same_metadata, same_webhook))
