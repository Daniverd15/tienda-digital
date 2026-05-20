"""Cliente HTTP a Inventory Service.

Patron: comunicacion REST sincrona entre servicios con timeout y fallback.
Si Inventory no responde a tiempo, devolvemos lista vacia y un flag
`inventory_available=False` al consumidor. Esto materializa el modo de
degradacion descrito en la seccion 13.3 del informe Fase 1 (Catalog sigue
mostrando productos con etiqueta de disponibilidad no confirmada).
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

INVENTORY_URL = os.getenv("INVENTORY_SERVICE_URL", "http://inventory-service:8003")


def get_variants_for_product(product_id: int, timeout_s: float = 2.0) -> tuple[list[dict], bool]:
    """Devuelve (variants, inventory_available)."""
    try:
        with httpx.Client(timeout=timeout_s) as client:
            r = client.get(f"{INVENTORY_URL}/products/{product_id}/variants")
        if r.status_code == 200:
            return r.json(), True
        logger.warning("Inventory respondio %s para product_id=%s", r.status_code, product_id)
        return [], r.status_code != 503
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        logger.warning("Inventory no disponible (%s); degradando", exc)
        return [], False
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error consultando Inventory: %s", exc)
        return [], False


def get_stock_summary(timeout_s: float = 2.0) -> tuple[dict, bool]:
    """Devuelve ({product_id: {stock, variant_count, min_price, max_price}}, inventory_available).

    Si Inventory no responde, devolvemos dict vacio + flag False. El listado de
    productos seguira sirviendose pero sin etiqueta de stock real (degradacion).
    """
    try:
        with httpx.Client(timeout=timeout_s) as client:
            r = client.get(f"{INVENTORY_URL}/stock-summary")
        if r.status_code == 200:
            return r.json(), True
        logger.warning("Inventory stock-summary respondio %s", r.status_code)
        return {}, False
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        logger.warning("Inventory no disponible para stock-summary (%s); degradando", exc)
        return {}, False
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error consultando stock-summary: %s", exc)
        return {}, False
