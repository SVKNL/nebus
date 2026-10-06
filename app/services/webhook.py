"""Отправка webhook клиенту с экспоненциальными повторами."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.constants import RETRY_BASE_DELAY_SECONDS, WEBHOOK_MAX_ATTEMPTS
from app.models.payment import Payment
from app.schemas.payment import WebhookPayload
from app.services.errors import PaymentProcessingError

logger = logging.getLogger(__name__)


class WebhookDeliveryError(PaymentProcessingError):
    """Webhook не доставлен после всех попыток HTTP."""


class WebhookNotifier:
    """HTTP-клиент для уведомления мерчанта о финальном статусе платежа."""

    def __init__(
        self,
        timeout_seconds: float | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self._timeout = timeout_seconds or settings.webhook_timeout_seconds
        self._client = client

    async def notify(self, payment: Payment) -> None:
        """POST JSON на payment.webhook_url.

        Повторы: 3 попытки, backoff 1с → 2с → 4с (wait_exponential, основание 2).
        Успехом считаем любой 2xx. 4xx/5xx и сетевые ошибки — повод для retry.
        """
        payload = WebhookPayload(
            payment_id=payment.id,
            status=payment.status,
            amount=payment.amount,
            currency=payment.currency,
            description=payment.description,
            metadata=payment.extra_metadata,
            processed_at=payment.processed_at,
        )
        body = payload.model_dump(mode="json")
        url = str(payment.webhook_url)
        try:
            if self._client is None:
                async with httpx.AsyncClient(
                    timeout=self._timeout,
                    follow_redirects=False,
                ) as client:
                    await self._post_with_retry(client, url, body)
            else:
                await self._post_with_retry(self._client, url, body)
        except (httpx.HTTPError, WebhookDeliveryError) as exc:
            logger.warning(
                "Webhook failed for payment_id=%s url=%s error=%s",
                payment.id,
                payment.webhook_url,
                exc,
            )
            raise WebhookDeliveryError(f"Не удалось доставить webhook: {exc}") from exc

        payment.webhook_sent_at = datetime.now(UTC)
        logger.info("Webhook delivered payment_id=%s", payment.id)

    async def _post_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        body: dict[str, Any],
    ) -> None:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(WEBHOOK_MAX_ATTEMPTS),
            wait=wait_exponential(
                multiplier=RETRY_BASE_DELAY_SECONDS,
                min=RETRY_BASE_DELAY_SECONDS,
                exp_base=2,
            ),
            retry=retry_if_exception_type((httpx.HTTPError, WebhookDeliveryError)),
            reraise=True,
        ):
            with attempt:
                await self._post_once(client, url, body)

    async def _post_once(
        self,
        client: httpx.AsyncClient,
        url: str,
        body: dict[str, Any],
    ) -> None:
        """Одна попытка доставки. Не-2xx превращаем в WebhookDeliveryError для retry."""
        response = await client.post(url, json=body)
        if response.is_success:
            return
        msg = f"HTTP {response.status_code} from webhook"
        logger.info("%s url=%s", msg, url)
        raise WebhookDeliveryError(msg)
