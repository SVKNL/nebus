"""Единый источник текущего времени в UTC."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """TZ-aware UTC. Нужен до refresh из БД, чтобы объект уже имел created_at."""
    return datetime.now(UTC)
