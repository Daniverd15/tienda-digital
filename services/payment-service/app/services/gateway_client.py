"""Cliente HTTP a la pasarela mock.

En el Bloque 5 (esta version): timeout corto + manejo de errores basico.
En el Bloque 6 se le agregara Circuit Breaker con contador en Redis.
"""
import logging
import os
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)

MOCK_URL = os.getenv("PAYMENT_MOCK_URL", "http://payment-mock:9000")


def charge(order_id: str, amount: float, currency: str = "COP",
           card_token: str | None = None, timeout_s: float = 5.0) -> dict:
    """Llama a la pasarela mock. Devuelve dict {status, transaction_reference, message}.

    Maneja:
    - APPROVED / REJECTED / PENDING (segun los centavos del monto)
    - timeout / connect_error -> PENDING (orden queda en pago pendiente)
    - 500 desde mock -> FAILED
    """
    payload = {"order_code": order_id, "amount": float(amount), "currency": currency}
    if card_token:
        payload["card_token"] = card_token
    try:
        with httpx.Client(timeout=timeout_s) as client:
            r = client.post(f"{MOCK_URL}/charge", json=payload)
        if r.status_code == 200:
            data = r.json()
            return {
                "status": data["status"],
                "transaction_reference": data["transaction_reference"],
                "message": data.get("message", ""),
            }
        if r.status_code >= 500:
            return {
                "status": "FAILED",
                "transaction_reference": f"err-{uuid4().hex[:10]}",
                "message": f"Pasarela respondio {r.status_code}",
            }
        return {
            "status": "REJECTED",
            "transaction_reference": f"reject-{uuid4().hex[:10]}",
            "message": r.text[:200],
        }
    except httpx.TimeoutException as exc:
        logger.warning("Pasarela timeout: %s", exc)
        return {
            "status": "PENDING",
            "transaction_reference": f"timeout-{uuid4().hex[:10]}",
            "message": "Pasarela no respondio a tiempo (PENDING)",
        }
    except httpx.HTTPError as exc:
        logger.warning("Pasarela error: %s", exc)
        return {
            "status": "FAILED",
            "transaction_reference": f"err-{uuid4().hex[:10]}",
            "message": f"Error de comunicacion: {exc}",
        }
