"""Lock distribuido con Redis (patron del informe Fase 1, seccion 13.3).

================================================================================
PROPOSITO
================================================================================
Materializa la garantia de consistencia bajo concurrencia: dos checkouts
simultaneos sobre la MISMA variante NO pueden reservar stock al mismo tiempo.
El primero que obtenga el lock procede; el segundo recibe TimeoutError (que
el caller traduce a HTTP 409 Conflict).

================================================================================
ALGORITMO (Redlock simplificado para una sola instancia)
================================================================================
1. Generamos un TOKEN unico (uuid4 hex) por cada intento de lock.
2. Hacemos `SET <key> <token> NX EX <ttl>` que es ATOMICO en Redis:
     - NX = solo escribe si la clave NO existe
     - EX = expiracion automatica en segundos (auto-cleanup si el proceso
            muere antes de liberar)
3. Para liberar, usamos un script LUA que verifica que el token coincide
   antes de borrar la clave. Esto evita que un proceso libere por error el
   lock que adquirio OTRO proceso (caso: el TTL expiro, otro entro, y
   nosotros vamos a liberar pensando que aun era nuestro).

================================================================================
DEGRADACION
================================================================================
Si Redis no esta disponible al startup del servicio, el cliente queda en None.
El context manager hace yield False (no-op) y el caller debe confiar en el
lock pesimista de MySQL (SELECT FOR UPDATE) que se hace dentro de la misma
transaccion. Asi el sistema sigue siendo correcto aunque pierda performance
y resiliencia ante el escenario chaos-monkey Redis.
"""
import logging
import os
from contextlib import contextmanager
from uuid import uuid4

import redis

from app.core.config import settings

# Logger del modulo. Aparecera en docker logs con el formato configurado en main.py
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Cliente Redis singleton del modulo.
# --------------------------------------------------------------------------
# Se inicializa UNA vez al importar el modulo. Si Redis no responde al ping,
# dejamos `_client = None` y el lock entra en modo degradado.
# decode_responses=True hace que .get() devuelva str en vez de bytes.
try:
    _client: redis.Redis | None = redis.from_url(settings.redis_url, decode_responses=True)
    _client.ping()  # ping sincrono — si falla, salta al except
    logger.info("Redis conectado: %s", settings.redis_url)
except Exception as exc:  # noqa: BLE001
    # Cualquier error de conexion (timeout, refused, dns) lo degrada a None.
    # NO levantamos: el servicio puede arrancar sin Redis (modo no-cluster).
    logger.warning("Redis NO disponible (%s). Lock distribuido degradado.", exc)
    _client = None


# --------------------------------------------------------------------------
# Script Lua para liberar el lock de forma ATOMICA.
# --------------------------------------------------------------------------
# Compara el valor actual de la clave con el token que nosotros guardamos
# al adquirir. Si coincide → DEL (libera). Si no coincide → 0 (otro proceso
# ya tomo el lock despues de que el nuestro expiro; no debemos tocarlo).
#
# Redis ejecuta este script de forma atomica: ningun otro comando puede
# entremedio entre el GET y el DEL.
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""


@contextmanager
def acquire(key: str, ttl_seconds: int = 5):
    """Adquiere un lock distribuido sobre `key` durante `ttl_seconds`.

    Uso esperado (en el caller, dentro de POST /reserve):

        with acquire(f"lock:variant:{variant_id}", ttl_seconds=5):
            # zona critica: nadie mas puede reservar esta misma variante
            ...

    Comportamiento:
    - Si se obtiene el lock → yield True, ejecuta el bloque, libera al salir.
    - Si NO se obtiene (otro proceso lo tiene) → levanta TimeoutError.
    - Si Redis esta caido → yield False (no-op): el caller DEBE garantizar
      consistencia por otro medio (tipicamente SELECT FOR UPDATE en MySQL).

    Parametros:
        key: identificador del recurso a bloquear. Convencion del proyecto:
             "lock:variant:<variant_id>" para variantes de inventario.
        ttl_seconds: tiempo maximo que el lock vive en Redis. Si el proceso
                     que adquirio el lock muere sin liberarlo, este TTL
                     evita un deadlock permanente. Default 5s — suficiente
                     para una operacion de reserva con SELECT FOR UPDATE.
    """
    # Caso 1: Redis no disponible → degradacion silenciosa.
    if _client is None:
        yield False  # No-op: el caller debe usar otro mecanismo
        return

    # Caso 2: Redis disponible → intentamos adquirir con SET NX EX.
    # Generamos un token unico para luego poder liberar SOLO si seguimos
    # siendo nosotros los duenios del lock.
    token = uuid4().hex
    acquired = False
    try:
        # SET <key> <token> NX EX <ttl> — Redis ejecuta esto atomicamente:
        # devuelve True si la clave estaba vacia (la creamos), False si ya
        # existia (otro la creo antes que nosotros).
        acquired = bool(_client.set(key, token, nx=True, ex=ttl_seconds))
        if not acquired:
            # Otro proceso tiene el lock. El caller traduce a HTTP 409.
            raise TimeoutError(f"Lock {key} ocupado por otra operacion concurrente.")
        # Cedemos el control al bloque `with` del caller.
        yield True
    finally:
        # Liberacion del lock. SOLO si nosotros lo adquirimos exitosamente.
        # Importante: usamos el script Lua para verificar el token y evitar
        # liberar un lock ajeno (escenario edge: nuestro proceso fue lento,
        # el TTL expiro, otro proceso adquirio el lock, y ahora venimos a
        # liberar pensando que es el nuestro).
        if acquired:
            try:
                _client.eval(_RELEASE_LUA, 1, key, token)
            except Exception as exc:  # noqa: BLE001
                # Si Redis cae justo al liberar, el TTL del lock lo limpiara
                # automaticamente en `ttl_seconds`. No es fatal.
                logger.warning("Fallo al liberar lock %s: %s", key, exc)


def health() -> bool:
    """Verifica si Redis esta accesible. Usado por GET /health del servicio.

    Devuelve True si responde PING, False si esta caido o no inicializado.
    """
    if _client is None:
        return False
    try:
        return _client.ping()
    except Exception:  # noqa: BLE001
        return False
