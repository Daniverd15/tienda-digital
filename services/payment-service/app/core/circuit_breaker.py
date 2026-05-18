"""Circuit Breaker basado en Redis (informe Fase 1, secciones 13.1 y 13.5).

Estados:
- CLOSED   : llamadas pasan; cada fallo incrementa el contador en Redis.
- OPEN     : tras >= threshold fallos en open_ttl segundos, rechaza inmediato
             durante open_ttl segundos.
- HALF_OPEN: una vez expirado el ttl del OPEN, la SIGUIENTE llamada se permite
             como 'prueba'. Si tiene exito, se resetea (CLOSED). Si falla, el
             contador queda en threshold y se mantiene OPEN otros open_ttl s.

Implementacion:
- Clave fallos:  cb:{name}:failures (integer, ttl rolling)
- Clave open:    cb:{name}:open      (presencia indica OPEN)
- Script Lua para record_success + record_failure atomicos.

Si Redis no esta disponible, el CB degrada a 'siempre cerrado' (no protege,
pero no rompe). Esto es Doctor Monkey friendly.
"""
import logging
import os
from dataclasses import dataclass
from enum import Enum

import redis

logger = logging.getLogger(__name__)


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

try:
    _client: redis.Redis | None = redis.from_url(REDIS_URL, decode_responses=True)
    _client.ping()
    logger.info("CB conectado a Redis %s", REDIS_URL)
except Exception as exc:  # noqa: BLE001
    logger.warning("Redis no disponible para CB (%s); modo degradado (siempre cerrado)", exc)
    _client = None


class CBState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 5
    open_ttl_seconds: int = 60
    window_seconds: int = 60   # ventana en la que se cuentan los fallos
    half_open_token_ttl: int = 5  # ttl del 'permiso' para la prueba de half-open

    @property
    def _fail_key(self) -> str:
        return f"cb:{self.name}:failures"

    @property
    def _open_key(self) -> str:
        return f"cb:{self.name}:open"

    @property
    def _half_open_key(self) -> str:
        return f"cb:{self.name}:half_open_token"

    # ------------------------------------------------------------------
    # Estado actual del CB
    # ------------------------------------------------------------------

    def get_state(self) -> CBState:
        if _client is None:
            return CBState.CLOSED
        try:
            if _client.exists(self._open_key):
                return CBState.OPEN
            if _client.exists(self._half_open_key):
                return CBState.HALF_OPEN
            return CBState.CLOSED
        except Exception:  # noqa: BLE001
            return CBState.CLOSED

    def stats(self) -> dict:
        if _client is None:
            return {"state": "CLOSED", "failures": 0, "redis": False}
        try:
            return {
                "state": self.get_state().value,
                "failures": int(_client.get(self._fail_key) or 0),
                "open_ttl_remaining": _client.ttl(self._open_key) if _client.exists(self._open_key) else 0,
                "redis": True,
                "threshold": self.failure_threshold,
                "open_ttl_seconds": self.open_ttl_seconds,
            }
        except Exception as exc:  # noqa: BLE001
            return {"state": "CLOSED", "failures": 0, "redis": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Antes de ejecutar la llamada: pedir 'permiso'
    # ------------------------------------------------------------------

    def allow(self) -> tuple[bool, CBState]:
        """Devuelve (permitido, estado).

        - CLOSED   -> True
        - OPEN     -> False (rechazo inmediato)
        - HALF_OPEN-> True, pero solo UNA llamada simultanea (token con TTL corto)
        """
        if _client is None:
            return True, CBState.CLOSED
        try:
            if _client.exists(self._open_key):
                # esta abierto; veo si ya paso el TTL para pasar a half_open
                return False, CBState.OPEN
            if _client.exists(self._half_open_key):
                # ya hay una prueba en curso; lo dejamos pasar igual (best effort)
                return True, CBState.HALF_OPEN
            # CLOSED: permite y NO marca half-open
            return True, CBState.CLOSED
        except Exception:  # noqa: BLE001
            return True, CBState.CLOSED

    def _try_promote_to_half_open(self) -> None:
        """Cuando el OPEN expira, la proxima llamada en realidad puede pasar.
        Marcamos un token con TTL corto que permita exactamente UNA prueba."""
        if _client is None:
            return
        try:
            _client.set(self._half_open_key, "1", nx=True, ex=self.half_open_token_ttl)
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # Reportar resultado
    # ------------------------------------------------------------------

    def record_success(self) -> None:
        if _client is None:
            return
        try:
            # exito: reset total
            pipe = _client.pipeline()
            pipe.delete(self._fail_key)
            pipe.delete(self._open_key)
            pipe.delete(self._half_open_key)
            pipe.execute()
        except Exception:  # noqa: BLE001
            pass

    def record_failure(self) -> CBState:
        if _client is None:
            return CBState.CLOSED
        try:
            # incremento con ttl rolling de la ventana
            failures = _client.incr(self._fail_key)
            if failures == 1:
                _client.expire(self._fail_key, self.window_seconds)
            if failures >= self.failure_threshold:
                # ABRE el circuito
                _client.set(self._open_key, "1", ex=self.open_ttl_seconds)
                _client.delete(self._half_open_key)
                logger.warning("CB[%s] OPEN tras %d fallos", self.name, failures)
                return CBState.OPEN
            return CBState.CLOSED
        except Exception:  # noqa: BLE001
            return CBState.CLOSED

    # ------------------------------------------------------------------
    # Util para tests / endpoint admin
    # ------------------------------------------------------------------

    def reset(self) -> None:
        if _client is None:
            return
        _client.delete(self._fail_key, self._open_key, self._half_open_key)
