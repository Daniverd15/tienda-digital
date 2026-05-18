"""Cliente HTTP a la pasarela mock con Circuit Breaker + reintentos.

Bloque 6 (esta version):
- Circuit Breaker basado en Redis (informe Fase 1, secciones 13.1 y 13.5).
- Reintentos con backoff exponencial para errores transitorios (timeout, 5xx).
- Si el CB esta OPEN, retorna inmediatamente SERVICE_UNAVAILABLE sin llamar al mock.
- HTTPException 502 cuando el CB rechaza; Commerce lo mapea a Order(PAGO_PENDIENTE).

Reglas:
- timeout / connection error / 5xx -> reintenta (max 2 reintentos = 3 intentos totales)
                                       y registra fallo en CB.
- REJECTED desde la pasarela: NO es fallo de la pasarela (es decision del banco) ->
  no incrementa el CB, no se reintenta.
- APPROVED / PENDING: resetea el CB.
"""
import logging
import os
import time
from uuid import uuid4

import httpx

from app.core.circuit_breaker import CBState, CircuitBreaker

logger = logging.getLogger(__name__)

MOCK_URL = os.getenv("PAYMENT_MOCK_URL", "http://payment-mock:9000")

# CB del Payment Service hacia la pasarela
provider_cb = CircuitBreaker(
    name="payment_provider",
    failure_threshold=5,
    open_ttl_seconds=60,
    window_seconds=60,
)


class CircuitOpenError(Exception):
    """El circuit breaker esta abierto; rechazo inmediato."""


def _backoff_seconds(attempt: int) -> float:
    # 0 -> 0.25, 1 -> 0.5, 2 -> 1.0
    return 0.25 * (2 ** attempt)


def charge(
    order_id: str,
    amount: float,
    currency: str = "COP",
    card_token: str | None = None,
    timeout_s: float = 5.0,
    max_attempts: int = 3,
) -> dict:
    """Llama a la pasarela mock con CB + reintentos. Devuelve dict con status."""
    allowed, state = provider_cb.allow()
    if not allowed:
        logger.warning("CB %s rechaza llamada (estado=%s)", provider_cb.name, state.value)
        raise CircuitOpenError(f"Circuit breaker abierto para pasarela. Reintenta en ~{provider_cb.open_ttl_seconds}s.")

    payload = {"order_code": order_id, "amount": float(amount), "currency": currency}
    if card_token:
        payload["card_token"] = card_token

    last_exception: Exception | None = None
    for attempt in range(max_attempts):
        try:
            with httpx.Client(timeout=timeout_s) as client:
                r = client.post(f"{MOCK_URL}/charge", json=payload)
            if r.status_code == 200:
                data = r.json()
                # APPROVED / REJECTED / PENDING segun mock
                status = data["status"]
                # APPROVED y PENDING resetean el CB (la pasarela responde sana)
                # REJECTED tambien (no es fallo de infra)
                provider_cb.record_success()
                return {
                    "status": status,
                    "transaction_reference": data["transaction_reference"],
                    "message": data.get("message", ""),
                }
            if r.status_code >= 500:
                # 5xx cuenta como fallo de infra
                logger.warning("Pasarela 5xx (intento %d/%d): %s", attempt + 1, max_attempts, r.status_code)
                new_state = provider_cb.record_failure()
                if new_state == CBState.OPEN:
                    return {
                        "status": "FAILED",
                        "transaction_reference": f"cb-{uuid4().hex[:8]}",
                        "message": "Pasarela inestable; circuito abierto.",
                    }
                if attempt < max_attempts - 1:
                    time.sleep(_backoff_seconds(attempt))
                    continue
                return {
                    "status": "FAILED",
                    "transaction_reference": f"err-{uuid4().hex[:10]}",
                    "message": f"Pasarela respondio {r.status_code} tras {max_attempts} intentos.",
                }
            # 4xx (no 5xx, no 200) lo tratamos como REJECTED sin reintento
            return {
                "status": "REJECTED",
                "transaction_reference": f"reject-{uuid4().hex[:10]}",
                "message": r.text[:200],
            }
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            last_exception = exc
            logger.warning("Pasarela TIMEOUT/CONN (intento %d/%d): %s", attempt + 1, max_attempts, exc)
            new_state = provider_cb.record_failure()
            if new_state == CBState.OPEN:
                return {
                    "status": "PENDING",
                    "transaction_reference": f"cb-{uuid4().hex[:8]}",
                    "message": "Pasarela inestable; circuito abierto. Quedo PENDING.",
                }
            if attempt < max_attempts - 1:
                time.sleep(_backoff_seconds(attempt))
                continue
            return {
                "status": "PENDING",
                "transaction_reference": f"timeout-{uuid4().hex[:10]}",
                "message": f"Pasarela no respondio tras {max_attempts} intentos.",
            }
        except httpx.HTTPError as exc:
            last_exception = exc
            provider_cb.record_failure()
            return {
                "status": "FAILED",
                "transaction_reference": f"err-{uuid4().hex[:10]}",
                "message": f"Error de comunicacion: {exc}",
            }

    # No deberiamos llegar aqui
    return {
        "status": "FAILED",
        "transaction_reference": f"err-{uuid4().hex[:10]}",
        "message": f"Sin respuesta tras reintentos: {last_exception}",
    }
