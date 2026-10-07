"""Подключение к RabbitMQ в фоне.

HTTP отвечает сразу. Если брокер лёг на старте, платежи всё равно пишутся в БД,
а relay подключится, когда очередь оживёт.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from app.messaging.broker import get_broker
from app.messaging.state import broker_state
from app.messaging.topology import declare_topology
from app.workers.outbox import OutboxPublisher

logger = logging.getLogger(__name__)

_RETRY_SECONDS = 2


async def supervise_broker(stop_event: asyncio.Event) -> None:
    """Крутит connect → топология → outbox, пока процесс не останавливают."""
    broker = get_broker()
    publisher = OutboxPublisher()
    while not stop_event.is_set():
        try:
            await broker.start()
            await declare_topology(broker)
            broker_state.connected = True
            logger.info("RabbitMQ connected, outbox relay is running")
            await publisher.run_forever(stop_event)
        except asyncio.CancelledError:
            raise
        except Exception:
            broker_state.connected = False
            logger.exception("RabbitMQ is unavailable, API keeps accepting payments")
            with suppress(Exception):
                await broker.stop()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=_RETRY_SECONDS)
            except TimeoutError:
                continue
        else:
            break
    broker_state.connected = False
    with suppress(Exception):
        await broker.stop()
