"""Clientes HTTP que Commerce usa para hablar con los demas microservicios.

Patron: comunicacion sincrona REST con timeout, manejo de errores y
propagacion de correlation_id. Estos clientes son los que ejecutan la SAGA
orquestada sincrona del checkout (informe Fase 1, seccion 11 y 11.0).
"""
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CATALOG_URL = os.getenv("CATALOG_SERVICE_URL", "http://catalog-service:8002")
INVENTORY_URL = os.getenv("INVENTORY_SERVICE_URL", "http://inventory-service:8003")
PAYMENT_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:8005")
AUTH_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001")


def _hdrs(token: str | None, correlation_id: str | None) -> dict:
    h: dict = {}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if correlation_id:
        h["X-Correlation-Id"] = correlation_id
    return h


class ServiceUnavailable(Exception):
    """El servicio destino no respondio (timeout o connection error)."""


# -----------------------------------------------------------------------------
# Catalog: detalle de producto + variante (snapshot para el carrito/orden)
# -----------------------------------------------------------------------------


def catalog_get_product(product_id: int, timeout_s: float = 2.0) -> dict | None:
    try:
        with httpx.Client(timeout=timeout_s) as c:
            r = c.get(f"{CATALOG_URL}/products/{product_id}")
        if r.status_code == 200:
            return r.json()
        return None
    except httpx.HTTPError as exc:
        logger.warning("Catalog product %s fallo: %s", product_id, exc)
        return None


def catalog_update_rating(product_id: int, average: float, count: int,
                          token: str, correlation_id: str | None = None,
                          timeout_s: float = 2.0) -> bool:
    try:
        with httpx.Client(timeout=timeout_s) as c:
            r = c.put(
                f"{CATALOG_URL}/admin/products/{product_id}/rating",
                json={"product_id": product_id, "average": average, "count": count},
                headers=_hdrs(token, correlation_id),
            )
        return r.status_code == 200
    except httpx.HTTPError as exc:
        logger.warning("Catalog rating update fallo: %s", exc)
        return False


# -----------------------------------------------------------------------------
# Inventory: get variant + reserve / confirm / release
# -----------------------------------------------------------------------------


def inventory_get_variant(variant_id: int, timeout_s: float = 2.0) -> dict | None:
    try:
        with httpx.Client(timeout=timeout_s) as c:
            r = c.get(f"{INVENTORY_URL}/variants/{variant_id}")
        if r.status_code == 200:
            return r.json()
        return None
    except httpx.HTTPError as exc:
        logger.warning("Inventory variant %s fallo: %s", variant_id, exc)
        return None


def inventory_reserve(order_id: str, items: list[dict], token: str,
                      correlation_id: str | None = None, timeout_s: float = 5.0) -> dict:
    """Llama POST /reserve. Devuelve dict del response. Lanza HTTPError o ServiceUnavailable."""
    try:
        with httpx.Client(timeout=timeout_s) as c:
            r = c.post(
                f"{INVENTORY_URL}/reserve",
                json={"order_id": order_id, "items": items, "ttl_seconds": 900},
                headers=_hdrs(token, correlation_id),
            )
        return {"status_code": r.status_code, "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else {}}
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        raise ServiceUnavailable(f"Inventory no disponible: {exc}") from exc


def inventory_confirm(order_id: str, token: str, correlation_id: str | None = None,
                      timeout_s: float = 5.0) -> bool:
    try:
        with httpx.Client(timeout=timeout_s) as c:
            r = c.post(
                f"{INVENTORY_URL}/confirm/{order_id}",
                headers=_hdrs(token, correlation_id),
            )
        return r.status_code == 200
    except httpx.HTTPError as exc:
        logger.warning("Inventory confirm fallo: %s", exc)
        return False


def inventory_release(order_id: str, reason: str, token: str,
                      correlation_id: str | None = None, timeout_s: float = 5.0) -> bool:
    try:
        with httpx.Client(timeout=timeout_s) as c:
            r = c.post(
                f"{INVENTORY_URL}/release",
                json={"order_id": order_id, "reason": reason},
                headers=_hdrs(token, correlation_id),
            )
        return r.status_code == 200
    except httpx.HTTPError as exc:
        logger.warning("Inventory release fallo: %s", exc)
        return False


# -----------------------------------------------------------------------------
# Payment
# -----------------------------------------------------------------------------


def payment_charge(order_id: str, amount: float, currency: str, token: str,
                   card_token: str | None = None, correlation_id: str | None = None,
                   timeout_s: float = 8.0) -> dict:
    """Devuelve dict {status_code, body}. Si Payment cae completamente, lanza."""
    try:
        with httpx.Client(timeout=timeout_s) as c:
            r = c.post(
                f"{PAYMENT_URL}/payments",
                json={"order_id": order_id, "amount": amount, "currency": currency,
                      "card_token": card_token},
                headers=_hdrs(token, correlation_id),
            )
        body: Any = {}
        try:
            body = r.json()
        except Exception:  # noqa: BLE001
            body = {"raw": r.text}
        return {"status_code": r.status_code, "body": body}
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        raise ServiceUnavailable(f"Payment no disponible: {exc}") from exc


# -----------------------------------------------------------------------------
# Auth (lookup de customers para admin)
# -----------------------------------------------------------------------------


def auth_get_customer(customer_id: int, token: str, timeout_s: float = 2.0) -> dict | None:
    try:
        with httpx.Client(timeout=timeout_s) as c:
            r = c.get(
                f"{AUTH_URL}/admin/customers/{customer_id}",
                headers=_hdrs(token, None),
            )
        if r.status_code == 200:
            return r.json()
        return None
    except httpx.HTTPError as exc:
        logger.warning("Auth get customer %s fallo: %s", customer_id, exc)
        return None
