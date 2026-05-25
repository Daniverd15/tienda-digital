"""Cliente HTTP a Catalog Service para validar referencias logicas a productos.

Cuando un admin crea una variante con product_id=X, Inventory verifica que
ese producto realmente existe en Catalog. Si Catalog esta caido, se permite
crear la variante en modo permisivo (Doctor Monkey: degradacion controlada).
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

CATALOG_URL = os.getenv("CATALOG_SERVICE_URL", "http://catalog-service:8002")


def product_exists(product_id: int, timeout_s: float = 2.0) -> bool | None:
    """Devuelve True si existe, False si no, None si Catalog no responde."""
    try:
        with httpx.Client(timeout=timeout_s) as client:
            r = client.get(f"{CATALOG_URL}/products/{product_id}")
        if r.status_code == 200:
            return True
        if r.status_code == 404:
            return False
        logger.warning("Catalog respondio %s para product_id=%s", r.status_code, product_id)
        return None
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        logger.warning("Catalog no disponible (%s); permitiendo creacion en modo degradado", exc)
        return None


def get_product(product_id: int, timeout_s: float = 2.0) -> dict | None:
    """Devuelve el producto publico de Catalog o None si no esta disponible."""
    try:
        with httpx.Client(timeout=timeout_s) as client:
            r = client.get(f"{CATALOG_URL}/products/{product_id}")
        if r.status_code == 200:
            return r.json()
        return None
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        logger.warning("Catalog no disponible para product_id=%s: %s", product_id, exc)
        return None
