"""Эмуляция внешнего платёжного шлюза.

В проде здесь был бы SDK эквайринга. Для задания: пауза 2–5 секунд
и 90% успешных списаний / 10% отказов.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Protocol

from app.constants import GATEWAY_MAX_DELAY, GATEWAY_MIN_DELAY, GATEWAY_SUCCESS_RATE
from app.models.payment import Payment, PaymentStatus

logger = logging.getLogger(__name__)


class PaymentGateway(Protocol):
    """Контракт шлюза: удобно подменять в тестах."""

    async def charge(self, payment: Payment) -> PaymentStatus:
        """Проводит платёж и возвращает терминальный статус."""


class EmulatedPaymentGateway:
    """Неопределённость результата имитирует реальный эквайринг."""

    def __init__(
        self,
        *,
        success_rate: float = GATEWAY_SUCCESS_RATE,
        rng: random.Random | None = None,
    ) -> None:
        self._success_rate = success_rate
        # SystemRandom — для эмуляции достаточно; не используется в криптографии.
        self._rng = rng or random.SystemRandom()

    async def charge(self, payment: Payment) -> PaymentStatus:
        """Ждём случайную задержку и бросаем монетку успеха."""
        delay_seconds = self._rng.uniform(
            GATEWAY_MIN_DELAY.total_seconds(),
            GATEWAY_MAX_DELAY.total_seconds(),
        )
        logger.info(
            "Gateway charge started payment_id=%s delay=%.2fs",
            payment.id,
            delay_seconds,
        )
        await asyncio.sleep(delay_seconds)
        if self._rng.random() < self._success_rate:
            logger.info("Gateway accepted payment_id=%s", payment.id)
            return PaymentStatus.SUCCEEDED
        logger.info("Gateway declined payment_id=%s", payment.id)
        return PaymentStatus.FAILED
