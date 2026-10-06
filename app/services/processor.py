"""Обработка одного сообщения payments.new: шлюз + статус + webhook."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.services.errors import PaymentNotFoundError, PaymentProcessingError
from app.services.gateway import EmulatedPaymentGateway, PaymentGateway
from app.services.webhook import WebhookNotifier

logger = logging.getLogger(__name__)


class PaymentProcessor:
    """Единственный consumer-обработчик по ТЗ: делает полный цикл платежа."""

    def __init__(
        self,
        session: AsyncSession,
        gateway: PaymentGateway | None = None,
        notifier: WebhookNotifier | None = None,
    ) -> None:
        self._session = session
        self._gateway = gateway or EmulatedPaymentGateway()
        self._notifier = notifier or WebhookNotifier()

    async def process(self, payment_id: UUID) -> None:
        """Идемпотентная обработка.

        1. Берём платёж FOR UPDATE, чтобы два delivery не списали дважды.
        2. Если ещё pending — эмулируем шлюз и пишем терминальный статус.
        3. Коммитим статус ДО webhook: падение сети не отменит списание.
        4. Если webhook ещё не уходил — отправляем с retry; успех снова коммитим.
        """
        payment = await self._lock_payment(payment_id)
        if not payment.is_terminal():
            status = await self._gateway.charge(payment)
            payment.status = status
            payment.processed_at = datetime.now(UTC)
            await self._session.commit()
            logger.info("Payment processed payment_id=%s status=%s", payment.id, payment.status)
        else:
            logger.info(
                "Skip gateway, already terminal payment_id=%s status=%s",
                payment.id,
                payment.status,
            )

        if payment.webhook_sent_at is not None:
            logger.info("Webhook already sent payment_id=%s", payment.id)
            return

        await self._notifier.notify(payment)
        await self._session.commit()

    async def _lock_payment(self, payment_id: UUID) -> Payment:
        stmt = select(Payment).where(Payment.id == payment_id).with_for_update()
        payment = await self._session.scalar(stmt)
        if payment is None:
            raise PaymentNotFoundError
        return payment


async def process_payment_message(
    session: AsyncSession,
    payment_id: UUID,
    *,
    gateway: PaymentGateway | None = None,
    notifier: WebhookNotifier | None = None,
) -> None:
    """Тонкая обёртка для FastStream-хендлера."""
    processor = PaymentProcessor(session, gateway=gateway, notifier=notifier)
    try:
        await processor.process(payment_id)
    except PaymentNotFoundError as exc:
        # Сообщения про «потерянный» id не ретраим бесконечно: это явный баг продюсера.
        raise PaymentProcessingError(f"Платёж {payment_id} не найден") from exc
