"""Проверка готовности: база обязательна, брокер и лаг outbox — для наблюдения."""

from __future__ import annotations

from sqlalchemy import func, select, text

from app.db.session import get_session_factory
from app.messaging.state import broker_state
from app.models.outbox import OutboxEvent


async def readiness_report() -> dict[str, object]:
    """database=false означает, что платежи принять нельзя."""
    database = await _database_ok()
    pending = await _unpublished_count() if database else None
    broker = broker_state.connected
    if not database:
        status = "not_ready"
    elif broker:
        status = "ready"
    else:
        status = "degraded"
    return {
        "status": status,
        "database": database,
        "broker": broker,
        "outbox_pending": pending,
    }


async def _database_ok() -> bool:
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _unpublished_count() -> int | None:
    try:
        factory = get_session_factory()
        async with factory() as session:
            stmt = (
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
            )
            value = await session.scalar(stmt)
        return int(value or 0)
    except Exception:
        return None
