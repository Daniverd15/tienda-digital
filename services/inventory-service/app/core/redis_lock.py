"""Lock distribuido con Redis (patron del informe Fase 1, seccion 13.3).

Materializa la garantia de consistencia en concurrencia: dos checkouts
simultaneos sobre la misma variante NO pueden reservar al mismo tiempo.
El primero que obtenga el lock procede; el segundo recibe 409 Conflict.

Algoritmo: SET <key> <token> NX EX <ttl> es atomico. El token (uuid) permite
liberar SOLO el lock que uno mismo creo (evita liberar uno ajeno por error).

Si Redis no esta disponible: degradacion a SELECT FOR UPDATE en MySQL desde
el caller (el lock devuelve un context manager 'no-op' que confia en la
transaccion).
"""
import logging
import os
from contextlib import contextmanager
from uuid import uuid4

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    _client: redis.Redis | None = redis.from_url(settings.redis_url, decode_responses=True)
    _client.ping()
    logger.info("Redis conectado: %s", settings.redis_url)
except Exception as exc:  # noqa: BLE001
    logger.warning("Redis NO disponible (%s). Lock distribuido degradado.", exc)
    _client = None


# Script Lua para liberar solo si el token coincide (atomico)
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""


@contextmanager
def acquire(key: str, ttl_seconds: int = 5):
    """Context manager: intenta adquirir lock; cede el lock al salir.

    Si no se puede adquirir en el TTL, levanta TimeoutError.
    Si Redis no esta disponible, hace no-op (caller debe usar lock de BD).
    """
    if _client is None:
        yield False  # No-op: caller debe garantizar consistencia por otra via
        return
    token = uuid4().hex
    acquired = False
    try:
        acquired = bool(_client.set(key, token, nx=True, ex=ttl_seconds))
        if not acquired:
            raise TimeoutError(f"Lock {key} ocupado por otra operacion concurrente.")
        yield True
    finally:
        if acquired:
            try:
                _client.eval(_RELEASE_LUA, 1, key, token)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Fallo al liberar lock %s: %s", key, exc)


def health() -> bool:
    if _client is None:
        return False
    try:
        return _client.ping()
    except Exception:  # noqa: BLE001
        return False
