"""Единая настройка логов для API и consumer."""

import logging

from app.config import get_settings


def setup_logging() -> None:
    """Один формат для обоих процессов."""
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
