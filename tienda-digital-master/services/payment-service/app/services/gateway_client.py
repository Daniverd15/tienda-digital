"""Cliente HTTP a la pasarela mock con Circuit Breaker + reintentos exponenciales.

================================================================================
PROPOSITO
================================================================================
Este modulo encapsula la unica funcion que llama a la pasarela de pago externa
(`charge`). Aplica las dos protecciones de resiliencia del informe Fase 1:

  1. Circuit Breaker (seccion 13.5): si la pasarela falla 5 veces consecutivas
     en 60s, el "fusible" se abre y rechaza llamadas inmediatas durante 60s
     sin tocar la pasarela. Asi protegemos al sistema de quedarse colgado
     esperando timeouts.

  2. Reintentos con backoff exponencial (seccion 13.1): si hay un error
     transitorio (timeout, 5xx), reintentamos 2 veces mas con esperas de
     250ms, 500ms, 1000ms. Estos errores son cosa de la infra (red intermitente,
     pasarela saturada un segundo) y muchas veces se resuelven solos.

================================================================================
DECISIONES IMPORTANTES
================================================================================
- REJECTED del banco NO es fallo de la pasarela: es decision del proveedor de
  pago. No incrementa el CB, no se reintenta (el banco diria lo mismo).
- APPROVED y PENDING resetean el CB (la pasarela respondio sana).
- 5xx, timeout y connection error SI cuentan como fallos de infra.
- 4xx (excepto los manejados como REJECTED) se tratan como fallos de negocio
  no reintentables (probablemente body mal formado).

================================================================================
COMPORTAMIENTO ANTE CB OPEN
================================================================================
Si el CB esta OPEN al momento de llamar:
  - Levantamos CircuitOpenError inmediatamente (sin tocar la pasarela).
  - El endpoint POST /payments captura la excepcion y devuelve HTTP 503.
  - El SAGA del Commerce traduce eso a "payment_unavailable" para el cliente
    y libera la reserva (compensacion).
"""
import logging
import os
import time
from uuid import uuid4

import httpx

from app.core.circuit_breaker import CBState, CircuitBreaker

logger = logging.getLogger(__name__)

# URL de la pasarela mock. En docker-compose apunta al contenedor payment-mock:9000.
# En tests/local-dev puede apuntar a otro endpoint via env var.
MOCK_URL = os.getenv("PAYMENT_MOCK_URL", "http://payment-mock:9000")

# --------------------------------------------------------------------------
# Instancia singleton del Circuit Breaker
# --------------------------------------------------------------------------
# Una instancia compartida del CB para toda la app (el estado vive en Redis,
# asi que esta variable Python solo encapsula la configuracion).
# - failure_threshold=5: tolerante a errores transitorios pero reactivo a caidas
# - open_ttl_seconds=60: tiempo de "espera curativa" antes de probar de nuevo
# - window_seconds=60: ventana rolling de conteo de fallos
provider_cb = CircuitBreaker(
    name="payment_provider",
    failure_threshold=5,
    open_ttl_seconds=60,
    window_seconds=60,
)


class CircuitOpenError(Exception):
    """El circuit breaker esta abierto; rechazo inmediato sin tocar la pasarela.

    El endpoint POST /payments la captura y devuelve HTTP 503 con un mensaje
    indicando que la pasarela esta temporalmente protegida.
    """


def _backoff_seconds(attempt: int) -> float:
    """Calcula el delay entre reintentos con backoff exponencial.

    attempt=0 → 0.25s (250ms)
    attempt=1 → 0.50s (500ms)
    attempt=2 → 1.00s (1s)

    Total worst case con 3 intentos: 250+500+1000 = 1.75s de espera + 3 timeouts
    de pasarela. Por eso el timeout default del cliente es 5s — para no
    pasarse de los 30s totales que tipicamente tolera un cliente HTTP.
    """
    return 0.25 * (2 ** attempt)


def charge(
    order_id: str,
    amount: float,
    currency: str = "COP",
    card_token: str | None = None,
    timeout_s: float = 5.0,
    max_attempts: int = 3,
) -> dict:
    """Llama a la pasarela mock para autorizar un cobro.

    Devuelve un dict con:
      - status: "APPROVED" | "REJECTED" | "PENDING" | "FAILED"
      - transaction_reference: id unico de la transaccion (para reconciliacion)
      - message: descripcion human-readable del resultado

    Levanta CircuitOpenError si el CB esta abierto al momento de llamar.

    Estrategia:
    1. Verificar CB.allow() → si OPEN, lanzar CircuitOpenError sin llamar.
    2. Hacer POST /charge a la pasarela.
    3. Segun la respuesta, decidir:
       - 200 + APPROVED/REJECTED/PENDING → record_success() en el CB, return.
       - 5xx → record_failure() en el CB. Si llega al threshold abre CB.
               Si quedan intentos, sleep con backoff y reintenta.
       - timeout/connect-error → mismo tratamiento que 5xx.
       - 4xx (no manejado) → tratar como REJECTED sin reintento.
    """
    # ─── 1. Verificar Circuit Breaker antes de tocar la pasarela ─────────
    allowed, state = provider_cb.allow()
    if not allowed:
        logger.warning("CB %s rechaza llamada (estado=%s)", provider_cb.name, state.value)
        raise CircuitOpenError(
            f"Circuit breaker abierto para pasarela. "
            f"Reintenta en ~{provider_cb.open_ttl_seconds}s."
        )

    # ─── 2. Preparar el payload de la pasarela ───────────────────────────
    # La pasarela mock espera order_code (no order_id) por consistencia con
    # el formato que usa Commerce internamente.
    payload = {"order_code": order_id, "amount": float(amount), "currency": currency}
    if card_token:
        payload["card_token"] = card_token

    # ─── 3. Loop de reintentos ───────────────────────────────────────────
    last_exception: Exception | None = None
    for attempt in range(max_attempts):
        try:
            # Cada intento abre y cierra su propio client (httpx.Client se
            # encarga del pool de conexiones internamente).
            with httpx.Client(timeout=timeout_s) as client:
                r = client.post(f"{MOCK_URL}/charge", json=payload)

            # Caso exitoso (200): la pasarela respondio algo coherente.
            # Resetea el CB porque la pasarela esta sana, sin importar si
            # aprobo o rechazo el pago concreto.
            if r.status_code == 200:
                data = r.json()
                status = data["status"]
                provider_cb.record_success()
                return {
                    "status": status,
                    "transaction_reference": data["transaction_reference"],
                    "message": data.get("message", ""),
                }

            # Caso 5xx: fallo de infra de la pasarela. CUENTA como fallo del CB.
            if r.status_code >= 500:
                logger.warning(
                    "Pasarela 5xx (intento %d/%d): %s",
                    attempt + 1, max_attempts, r.status_code
                )
                new_state = provider_cb.record_failure()
                # Si este fallo abrio el CB, no tiene sentido reintentar:
                # el siguiente intento dentro del mismo handler veria
                # OPEN y rechazaria igual.
                if new_state == CBState.OPEN:
                    return {
                        "status": "FAILED",
                        "transaction_reference": f"cb-{uuid4().hex[:8]}",
                        "message": "Pasarela inestable; circuito abierto.",
                    }
                # Si quedan intentos: sleep con backoff y reintenta.
                if attempt < max_attempts - 1:
                    time.sleep(_backoff_seconds(attempt))
                    continue
                # Sin intentos restantes: devolvemos FAILED.
                return {
                    "status": "FAILED",
                    "transaction_reference": f"err-{uuid4().hex[:10]}",
                    "message": f"Pasarela respondio {r.status_code} tras {max_attempts} intentos.",
                }

            # Caso 4xx no manejado especificamente: lo tratamos como REJECTED
            # porque probablemente el body iba mal formado. No reintentamos
            # (mismo input → mismo error).
            return {
                "status": "REJECTED",
                "transaction_reference": f"reject-{uuid4().hex[:10]}",
                "message": r.text[:200],
            }

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            # Caso timeout / conn-refused: fallo de infra puro. CUENTA en CB.
            last_exception = exc
            logger.warning(
                "Pasarela TIMEOUT/CONN (intento %d/%d): %s",
                attempt + 1, max_attempts, exc
            )
            new_state = provider_cb.record_failure()
            # Si este fallo abrio el CB → quedo PENDING (no FAILED) porque
            # no sabemos si la pasarela proceso el pago o no. El worker
            # reconciler intentara verificar mas tarde.
            if new_state == CBState.OPEN:
                return {
                    "status": "PENDING",
                    "transaction_reference": f"cb-{uuid4().hex[:8]}",
                    "message": "Pasarela inestable; circuito abierto. Quedo PENDING.",
                }
            if attempt < max_attempts - 1:
                time.sleep(_backoff_seconds(attempt))
                continue
            # Sin intentos restantes: PENDING para que el reconciler lo retome.
            return {
                "status": "PENDING",
                "transaction_reference": f"timeout-{uuid4().hex[:10]}",
                "message": f"Pasarela no respondio tras {max_attempts} intentos.",
            }

        except httpx.HTTPError as exc:
            # Otros errores HTTP no esperados (parseo, SSL, etc.). CUENTA en CB
            # pero no reintentamos (probablemente sea problema del cliente, no
            # de la pasarela).
            last_exception = exc
            provider_cb.record_failure()
            return {
                "status": "FAILED",
                "transaction_reference": f"err-{uuid4().hex[:10]}",
                "message": f"Error de comunicacion: {exc}",
            }

    # Defensivo: el codigo nunca deberia llegar aqui porque cada path del for
    # tiene un return. Si por algun bug pasa, devolvemos FAILED seguro.
    return {
        "status": "FAILED",
        "transaction_reference": f"err-{uuid4().hex[:10]}",
        "message": f"Sin respuesta tras reintentos: {last_exception}",
    }
