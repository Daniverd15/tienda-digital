"""Cache-Aside con Redis.

Patron del informe Fase 1: el servicio consulta Redis primero; si miss, lee
MySQL y poblar cache con TTL. La invalidacion se hace al editar via /admin/*
(invalidate_prefix). En Nivel 3 se agregara invalidacion por eventos AMQP
(StockUpdated desde Inventory para invalidar /products que muestren stock).

Si Redis falla, el cache degrada a no-op (modo Doctor Monkey: el sistema
sigue funcionando, solo mas lento).
"""
import json
import logging
from typing import Any

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    _client: redis.Redis | None = redis.from_url(settings.redis_url, decode_responses=True)
    _client.ping()
    logger.info("Redis conectado: %s", settings.redis_url)
except Exception as exc:  # noqa: BLE001
    logger.warning("Redis NO disponible (%s). Cache deshabilitado.", exc)
    _client = None


def get(key: str) -> Any | None:
    if _client is None:
        return None
    try:
        raw = _client.get(key)
        return json.loads(raw) if raw else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cache GET fallo %s: %s", key, exc)
        return None


def set_(key: str, value: Any, ttl_seconds: int = 60) -> None:
    if _client is None:
        return
    try:
        _client.setex(key, ttl_seconds, json.dumps(value, default=str))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cache SET fallo %s: %s", key, exc)


def invalidate_prefix(prefix: str) -> int:
    """Elimina todas las claves cuyo nombre comienza con prefix."""
    if _client is None:
        return 0
    try:
        deleted = 0
        for key in _client.scan_iter(match=f"{prefix}*"):
            _client.delete(key)
            deleted += 1
        return deleted
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cache INVALIDATE %s* fallo: %s", prefix, exc)
        return 0


def health() -> bool:
    if _client is None:
        return False
    try:
        return _client.ping()
    except Exception:  # noqa: BLE001
        return False
