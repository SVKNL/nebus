"""Зависимости FastAPI: аутентификация и сессия БД."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_session
from app.services.payment import PaymentService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def require_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    """Статический API-ключ из ТЗ: заголовок X-API-Key на всех боевых эндпоинтах.

    Сравнение через compare_digest, чтобы не светить ключ по времени ответа.
    Отсутствие или неверный ключ — 401, без деталей.
    """
    expected = get_settings().api_key
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key",
        )


async def get_payment_service(session: SessionDep) -> PaymentService:
    """Сервисный слой с сессией текущего запроса."""
    return PaymentService(session)
