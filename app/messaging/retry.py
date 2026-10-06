"""Политика повторной обработки сообщений и отправки в DLQ."""

from app.constants import MAX_PROCESS_ATTEMPTS, RETRY_BASE_DELAY_SECONDS

ATTEMPT_HEADER = "x-attempt"


def parse_attempt(headers: dict | None) -> int:
    """Читаем номер уже выполненных попыток из заголовка AMQP (0 — первая)."""
    if not headers:
        return 0
    raw = headers.get(ATTEMPT_HEADER, 0)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def retry_delay_seconds(attempt: int) -> int:
    """Экспоненциальная задержка перед следующей попыткой: 1, 2, 4, ... секунд."""
    return RETRY_BASE_DELAY_SECONDS * (2**attempt)


def should_dead_letter(attempt: int) -> bool:
    """True, если текущая попытка последняя (всего MAX_PROCESS_ATTEMPTS)."""
    return attempt >= MAX_PROCESS_ATTEMPTS - 1
