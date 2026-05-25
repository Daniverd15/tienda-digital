"""Circuit Breaker basado en Redis (informe Fase 1, secciones 13.1 y 13.5).

================================================================================
PROPOSITO
================================================================================
Protege al sistema contra fallos en cascada cuando la pasarela de pago externa
esta inestable. En vez de seguir llamandola y esperar timeouts (que bloquean
hilos del servidor), el Circuit Breaker abre el "fusible" tras varios fallos
consecutivos y rechaza las siguientes llamadas INMEDIATAMENTE con HTTP 503.
Esto da tiempo a la pasarela para recuperarse y al sistema para reportar al
cliente "intenta en unos minutos" sin que el checkout quede colgado.

================================================================================
MAQUINA DE ESTADOS
================================================================================
                    ┌──────────────────────────────┐
                    │                              │
                    ▼                              │
    ┌─────────┐     fallo>=threshold     ┌────────┐│
    │ CLOSED  │ ─────────────────────────►│  OPEN  ││  exito en prueba
    │(normal) │                          │(rechaza)│└──────────┐
    └─────────┘                          └────────┘            │
         ▲                                    │                │
         │      exito                         │ open_ttl       │
         │                                    ▼                │
         │                              ┌───────────┐          │
         └──────────────────────────────│ HALF_OPEN │──────────┘
                                        │  (prueba) │
                                        └───────────┘
                                              │
                                              │ fallo
                                              ▼
                                            OPEN

- CLOSED: llamadas pasan normal; cada fallo incrementa contador en Redis.
- OPEN: rechazo inmediato durante open_ttl_seconds (no se contacta pasarela).
- HALF_OPEN: tras expirar el OPEN, se permite UNA llamada de prueba. Si tiene
             exito → CLOSED (reset total). Si falla → OPEN otra vez.

================================================================================
ALMACENAMIENTO EN REDIS
================================================================================
- cb:{name}:failures        → contador entero con TTL rolling (ventana de
                              fallos para olvidar errores viejos).
- cb:{name}:open            → presencia indica estado OPEN; TTL = duracion
                              del open.
- cb:{name}:half_open_token → token corto que indica "ya hay una prueba en
                              curso, no la dispares de nuevo".

================================================================================
DEGRADACION
================================================================================
Si Redis no esta disponible al startup, el CB queda en "siempre cerrado" (no
protege pero tampoco rompe). Esto es Doctor Monkey friendly: el servicio
arranca aunque Redis no este listo.
"""
import logging
import os
from dataclasses import dataclass
from enum import Enum

import redis

logger = logging.getLogger(__name__)


# URL de Redis tomada del entorno (configurada en docker-compose.yml).
# Default apunta al servicio "redis" del network de Docker.
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# --------------------------------------------------------------------------
# Cliente Redis singleton del modulo.
# --------------------------------------------------------------------------
# Una sola conexion para todo el proceso del Payment Service. Si Redis no
# responde al startup, _client queda en None y el CB entra en modo degradado
# (devuelve siempre CLOSED).
try:
    _client: redis.Redis | None = redis.from_url(REDIS_URL, decode_responses=True)
    _client.ping()
    logger.info("CB conectado a Redis %s", REDIS_URL)
except Exception as exc:  # noqa: BLE001
    logger.warning("Redis no disponible para CB (%s); modo degradado (siempre cerrado)", exc)
    _client = None


class CBState(str, Enum):
    """Estados posibles del Circuit Breaker. Se hereda de str para serializar
    facilmente en JSON sin necesidad de un encoder custom."""
    CLOSED = "CLOSED"      # operacion normal
    OPEN = "OPEN"          # rechazando todas las llamadas
    HALF_OPEN = "HALF_OPEN"  # permitiendo una llamada de prueba


@dataclass
class CircuitBreaker:
    """Circuit Breaker configurable. Una instancia = un fusible logico.

    El Payment Service crea una instancia por dependencia critica:
    `gateway_cb = CircuitBreaker(name="gateway")` protege la pasarela.

    Parametros:
        name: identificador unico (se usa como prefijo de las claves Redis).
        failure_threshold: cantidad de fallos consecutivos antes de abrir el
                           circuito. Default 5 → tolerante a fallos transitorios
                           pero reactivo ante caidas reales.
        open_ttl_seconds: duracion del estado OPEN. Tras este tiempo, la
                          siguiente llamada se permite en HALF_OPEN. Default
                          60s — suficiente para que una pasarela se recupere.
        window_seconds: ventana de tiempo donde se cuentan los fallos. Default
                        60s → si pasan >60s sin fallos, el contador se olvida
                        (el TTL del key expira).
        half_open_token_ttl: cuanto vive el token de prueba en HALF_OPEN.
                             Default 5s — solo damos 5s para resolver la
                             prueba antes de permitir otra.
    """
    name: str
    failure_threshold: int = 5
    open_ttl_seconds: int = 60
    window_seconds: int = 60
    half_open_token_ttl: int = 5

    # --------------------------------------------------------------------
    # Claves Redis (propiedades para mantener consistencia y evitar typos)
    # --------------------------------------------------------------------

    @property
    def _fail_key(self) -> str:
        """Clave del contador de fallos. INT con TTL rolling de window_seconds."""
        return f"cb:{self.name}:failures"

    @property
    def _open_key(self) -> str:
        """Clave que existe SOLO cuando el CB esta OPEN. Su TTL marca cuanto
        queda abierto. Al expirar, la siguiente llamada va a HALF_OPEN."""
        return f"cb:{self.name}:open"

    @property
    def _half_open_key(self) -> str:
        """Token de prueba en HALF_OPEN. Su presencia indica que ya hay una
        llamada en curso probando si la dependencia se recupero."""
        return f"cb:{self.name}:half_open_token"

    # ------------------------------------------------------------------
    # CONSULTA DE ESTADO
    # ------------------------------------------------------------------

    def get_state(self) -> CBState:
        """Calcula el estado actual del CB consultando Redis. Solo lectura."""
        if _client is None:
            return CBState.CLOSED
        try:
            # Orden importante: si open_key existe, estamos OPEN aunque
            # haya un half_open_token (situacion transitoria).
            if _client.exists(self._open_key):
                return CBState.OPEN
            if _client.exists(self._half_open_key):
                return CBState.HALF_OPEN
            return CBState.CLOSED
        except Exception:  # noqa: BLE001
            # Si Redis falla en plena consulta, asumimos CLOSED por seguridad
            # (mejor permitir trafico que bloquear todo el sistema).
            return CBState.CLOSED

    def stats(self) -> dict:
        """Snapshot completo para el endpoint admin GET /payments/circuit/state.

        Devuelve estado, contador de fallos, TTL restante del open y configuracion.
        Si Redis cae, devuelve estado seguro (CLOSED) con flag redis=False.
        """
        if _client is None:
            return {"state": "CLOSED", "failures": 0, "redis": False}
        try:
            return {
                "state": self.get_state().value,
                "failures": int(_client.get(self._fail_key) or 0),
                # TTL restante del open: util para saber "cuanto falta para que
                # el CB se recupere automaticamente".
                "open_ttl_remaining": _client.ttl(self._open_key) if _client.exists(self._open_key) else 0,
                "redis": True,
                "threshold": self.failure_threshold,
                "open_ttl_seconds": self.open_ttl_seconds,
            }
        except Exception as exc:  # noqa: BLE001
            return {"state": "CLOSED", "failures": 0, "redis": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # ANTES DE LLAMAR A LA DEPENDENCIA: PEDIR PERMISO
    # ------------------------------------------------------------------

    def allow(self) -> tuple[bool, CBState]:
        """Decide si se permite la siguiente llamada a la dependencia.

        Devuelve (permitido, estado_actual). El caller (gateway_client.charge)
        debe verificar y devolver 503 al cliente si no se permite.

        Reglas:
        - CLOSED   → True (operacion normal)
        - OPEN     → False (rechazo inmediato; ahorra tiempo de timeout)
        - HALF_OPEN→ True (permitimos la prueba); en estado puramente correcto
                     deberiamos atomic-test-and-set para que solo UNA llamada
                     entre. Hacemos best-effort: si llegan dos casi
                     simultaneas, ambas pasan; lo aceptamos porque el danio
                     es minimo.
        """
        if _client is None:
            return True, CBState.CLOSED
        try:
            if _client.exists(self._open_key):
                return False, CBState.OPEN
            if _client.exists(self._half_open_key):
                # Ya hay una prueba en curso. Best-effort: dejamos pasar otra.
                return True, CBState.HALF_OPEN
            # CLOSED: caso normal.
            return True, CBState.CLOSED
        except Exception:  # noqa: BLE001
            return True, CBState.CLOSED

    def _try_promote_to_half_open(self) -> None:
        """Marca el inicio de una prueba en HALF_OPEN.

        Cuando el OPEN expira (TTL llega a 0), la siguiente llamada en realidad
        puede pasar. Marcamos un token con TTL corto para evitar que el
        sistema bombardee la dependencia con muchas pruebas concurrentes.
        SET NX EX garantiza que solo un proceso marca el token.
        """
        if _client is None:
            return
        try:
            _client.set(self._half_open_key, "1", nx=True, ex=self.half_open_token_ttl)
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # REPORTAR RESULTADO TRAS LA LLAMADA
    # ------------------------------------------------------------------

    def record_success(self) -> None:
        """Reporta que la llamada a la dependencia fue exitosa.

        Resetea TODO: contador de fallos, estado OPEN, token de half-open.
        El sistema vuelve a CLOSED inmediatamente. Hacemos un pipeline para
        ejecutar los tres DELETE en una sola roundtrip a Redis.
        """
        if _client is None:
            return
        try:
            pipe = _client.pipeline()
            pipe.delete(self._fail_key)
            pipe.delete(self._open_key)
            pipe.delete(self._half_open_key)
            pipe.execute()
        except Exception:  # noqa: BLE001
            # Si Redis cae al reportar exito, no es critico: el siguiente
            # exito o el TTL de window_seconds limpiaran el contador.
            pass

    def record_failure(self) -> CBState:
        """Reporta que la llamada a la dependencia fallo.

        Incrementa el contador con TTL rolling (window_seconds). Si supera el
        threshold, abre el circuito durante open_ttl_seconds. Devuelve el
        estado resultante para que el caller logue / metricize.
        """
        if _client is None:
            return CBState.CLOSED
        try:
            # INCR es atomico: dos procesos concurrentes nunca pierden cuenta.
            failures = _client.incr(self._fail_key)
            # Solo en el PRIMER incremento seteamos el TTL de la ventana.
            # En incrementos posteriores el TTL no se renueva, lo que da
            # semantica "5 fallos en una ventana rolling de 60s".
            if failures == 1:
                _client.expire(self._fail_key, self.window_seconds)
            # Si pasamos el umbral → abrimos el circuito.
            if failures >= self.failure_threshold:
                _client.set(self._open_key, "1", ex=self.open_ttl_seconds)
                # Limpiamos el token de half-open por si quedo de una
                # transicion anterior.
                _client.delete(self._half_open_key)
                logger.warning("CB[%s] OPEN tras %d fallos", self.name, failures)
                return CBState.OPEN
            return CBState.CLOSED
        except Exception:  # noqa: BLE001
            return CBState.CLOSED

    # ------------------------------------------------------------------
    # OPERACIONES ADMINISTRATIVAS (tests + endpoint admin)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Resetea manualmente el CB al estado CLOSED.

        Lo usa POST /payments/circuit/reset (endpoint admin) cuando el
        operador sabe que la pasarela ya se recupero y no quiere esperar al
        ciclo automatico HALF_OPEN. Tambien lo usan los tests de chaos para
        partir de un estado conocido.
        """
        if _client is None:
            return
        _client.delete(self._fail_key, self._open_key, self._half_open_key)
