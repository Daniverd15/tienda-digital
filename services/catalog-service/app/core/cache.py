"""Cache-Aside con Redis para el Catalog Service.

================================================================================
PROPOSITO
================================================================================
Materializa el patron Cache-Aside (Lazy Loading) del informe Fase 1, seccion
13.2. El objetivo es reducir la carga sobre MySQL para datos que cambian
poco (categorias, productos publicados, configuracion de la tienda) y que
se consultan mucho (cada vez que un cliente abre el catalogo).

================================================================================
FLUJO CACHE-ASIDE
================================================================================

   ┌──────────┐  GET key   ┌──────────┐
   │  Caller  │ ─────────► │  Redis   │
   └──────────┘            └──────────┘
        │                       │
        │   ┌── HIT (devuelve cached) ──► retorna
        │   │
        │   └── MISS (returns None)
        │
        │   ┌──────────┐ SELECT ┌──────────┐
        └──►│  MySQL   │ ──────►│  MySQL   │
            └──────────┘        └──────────┘
                  │
                  ▼
            (cache.set_ con TTL)
                  │
                  ▼
              retorna

================================================================================
INVALIDACION
================================================================================
- Al editar via /admin/categories, /admin/products, /admin/store/settings, etc.
  el handler invoca invalidate_prefix() para limpiar las claves afectadas.
- Cada clave tiene TTL (60s para listas, 300s para settings poco mutables)
  como red de seguridad: si olvidamos invalidar en algun edit, en el peor
  caso el cliente ve datos viejos hasta que el TTL expire.

================================================================================
DEGRADACION (Doctor Monkey friendly)
================================================================================
Si Redis no esta disponible al startup, _client queda en None y todas las
funciones se vuelven no-op:
- get() devuelve None (siempre MISS, el caller va a MySQL)
- set_() no hace nada (no se cachea)
- invalidate_prefix() devuelve 0

El catalogo sigue funcionando, solo mas lento (cada request golpea MySQL).
"""
import json
import logging
from typing import Any

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Cliente Redis singleton del modulo.
# --------------------------------------------------------------------------
# Una sola conexion para todo el proceso del Catalog Service.
# decode_responses=True hace que .get() devuelva str en vez de bytes.
try:
    _client: redis.Redis | None = redis.from_url(settings.redis_url, decode_responses=True)
    _client.ping()
    logger.info("Redis conectado: %s", settings.redis_url)
except Exception as exc:  # noqa: BLE001
    # Cualquier error de conexion: el cache pasa a "modo deshabilitado".
    logger.warning("Redis NO disponible (%s). Cache deshabilitado.", exc)
    _client = None


def get(key: str) -> Any | None:
    """Lee un valor del cache. Devuelve None si MISS o si Redis cae.

    Internamente:
    1. Si _client es None (Redis caido al startup) → None inmediato.
    2. Llama Redis.GET → si la clave existe, devuelve el JSON deserializado.
    3. Si la clave no existe (MISS) → None.
    4. Si Redis cae en runtime → loguea WARN y devuelve None.

    Convencion de claves del catalog: `catalog:<entidad>[:<filtro>]`
      - "catalog:categories"        → lista de categorias activas
      - "catalog:products:q=...:cat=..." → resultado del listado con filtros
      - "catalog:store:settings"    → configuracion de la tienda
    """
    if _client is None:
        return None
    try:
        raw = _client.get(key)
        # Si no existe (None), no llamamos a json.loads para evitar TypeError.
        return json.loads(raw) if raw else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cache GET fallo %s: %s", key, exc)
        return None


def set_(key: str, value: Any, ttl_seconds: int = 60) -> None:
    """Escribe un valor al cache con TTL en segundos.

    `set_` se llama asi (con underscore final) porque `set` es palabra
    reservada en Python (built-in del tipo set).

    Internamente usa SETEX (atomic set + expire) para garantizar que la
    clave nunca quede sin TTL (lo que causaria fuga de memoria en Redis).

    El default `default=str` en json.dumps permite serializar tipos no
    directamente JSON-able (datetime, Decimal) convirtiendolos a su repr
    de string. Es suficiente para datos de lectura del catalogo.
    """
    if _client is None:
        return
    try:
        _client.setex(key, ttl_seconds, json.dumps(value, default=str))
    except Exception as exc:  # noqa: BLE001
        # Si Redis falla al escribir, no es fatal: el sistema funciona sin
        # cache, solo mas lento en la siguiente request.
        logger.warning("Cache SET fallo %s: %s", key, exc)


def invalidate_prefix(prefix: str) -> int:
    """Elimina todas las claves cuyo nombre comienza con `prefix`.

    Lo invocan los endpoints admin tras editar/crear/archivar para invalidar
    el cache. Ejemplos:
      - Al editar una categoria → invalidate_prefix("catalog:categories")
                                  invalidate_prefix("catalog:products")
      - Al editar la tienda     → invalidate_prefix("catalog:store")

    Usa SCAN (no KEYS) para no bloquear Redis si hay muchas claves: SCAN
    itera con cursores y no toma lock. Devuelve la cantidad de claves
    eliminadas (para logging/debug).
    """
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
    """Verifica si Redis esta accesible. Usado por GET /health del servicio."""
    if _client is None:
        return False
    try:
        return _client.ping()
    except Exception:  # noqa: BLE001
        return False
