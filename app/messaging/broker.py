"""Фабрика брокера. Топологию объявляет declare_topology после connect."""

from functools import lru_cache

from faststream.rabbit import RabbitBroker

from app.config import get_settings


@lru_cache
def get_broker() -> RabbitBroker:
    """Один брокер на процесс. Очереди здесь не регистрируем: publisher() их не создаёт."""
    return RabbitBroker(str(get_settings().rabbitmq_url))
