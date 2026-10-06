"""Единый брокер FastStream для API (outbox) и consumer."""

from functools import lru_cache

from faststream.rabbit import RabbitBroker

from app.config import get_settings
from app.messaging.queues import (
    dead_letter_exchange,
    dead_letter_queue,
    payments_exchange,
    payments_new_queue,
    retry_queue,
)


@lru_cache
def get_broker() -> RabbitBroker:
    """Один брокер на процесс: publisher и subscriber шарят соединение.

    Регистрация publisher'ов заранее объявляет exchange/queue/bind,
    поэтому API может публиковать события ещё до старта consumer.
    """
    settings = get_settings()
    broker = RabbitBroker(str(settings.rabbitmq_url))
    broker.publisher(payments_new_queue, payments_exchange, persist=True)
    broker.publisher(retry_queue, payments_exchange, persist=True)
    broker.publisher(dead_letter_queue, dead_letter_exchange, persist=True)
    return broker
