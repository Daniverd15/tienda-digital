"""Clientes HTTP que Commerce usa para hablar con los demas microservicios.

================================================================================
PROPOSITO
================================================================================
Patron: comunicacion sincrona REST entre microservicios con timeout, manejo
de errores y propagacion de correlation_id. Estos clientes son los que
ejecutan la SAGA orquestada sincrona del checkout (informe Fase 1, secciones
11 y 11.0).

================================================================================
CONVENCIONES
================================================================================
- Todas las funciones reciben `token` (JWT del usuario que origino la
  request original) y `correlation_id` (inyectado por el gateway). El JWT
  se reenvia tal cual: cada microservicio destino lo valida con la misma
  clave HS256 compartida (SSO sin call-back al Auth Service).
- Las URLs base se toman de variables de entorno (CATALOG_SERVICE_URL,
  INVENTORY_SERVICE_URL, etc.) configuradas en docker-compose.yml para que
  apunten al nombre de contenedor (`http://catalog-service:8002`).
- Los timeouts son cortos por defecto (2–5s) para que un servicio lento
  no bloquee al orquestador. Si supera el timeout, levantamos
  ServiceUnavailable que el SAGA traduce a HTTP 503 al cliente.

================================================================================
COMPONENTES
================================================================================
- catalog_get_product, catalog_update_rating: Commerce → Catalog
- inventory_get_variant, inventory_get_variants_by_ids,
  inventory_reserve, inventory_confirm, inventory_release: Commerce → Inventory
- payment_charge: Commerce → Payment
- auth_get_customer: Commerce → Auth (para admin que consulta clientes)
"""
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# URLs de los servicios destino. Tomadas del entorno con fallback al nombre
# de contenedor (asumiendo que corren en la misma network Docker tienda_net).
# --------------------------------------------------------------------------
CATALOG_URL   = os.getenv("CATALOG_SERVICE_URL",   "http://catalog-service:8002")
INVENTORY_URL = os.getenv("INVENTORY_SERVICE_URL", "http://inventory-service:8003")
PAYMENT_URL   = os.getenv("PAYMENT_SERVICE_URL",   "http://payment-service:8005")
AUTH_URL      = os.getenv("AUTH_SERVICE_URL",      "http://auth-service:8001")


def _hdrs(token: str | None, correlation_id: str | None) -> dict:
    """Construye los headers HTTP que se envian a todos los microservicios.

    - Authorization: Bearer <jwt> → permite validar localmente al destino
      sin call-back al Auth Service (SSO con JWT compartido).
    - X-Correlation-Id → propaga el id que el gateway inyecto al request
      original para que TODA la cadena de logs comparta el mismo hilo y
      podamos reconstruir la "pelicula" de una sesion en la bitacora.
    """
    h: dict = {}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if correlation_id:
        h["X-Correlation-Id"] = correlation_id
    return h


class ServiceUnavailable(Exception):
    """El servicio destino no respondio (timeout o connection error).

    Se distingue de un HTTPError "comun" (4xx/5xx con respuesta) porque
    estos errores son INFRA — el servicio esta caido — y el SAGA los
    convierte en 503 + compensacion (libera reserva, no crea Order).
    """


# ═════════════════════════════════════════════════════════════════════════
# Catalog: detalle de producto + actualizacion de rating
# ═════════════════════════════════════════════════════════════════════════


def catalog_get_product(product_id: int, timeout_s: float = 2.0) -> dict | None:
    """Consulta el detalle de un producto en Catalog (sin autenticacion).

    Lo usa Commerce para enriquecer el carrito con snapshot de nombre,
    descripcion e imagen del producto al momento de agregarlo. Si Catalog
    cae, devolvemos None y el caller decide que hacer (no es critico).

    Devuelve dict del producto o None si no existe / no responde.
    """
    try:
        with httpx.Client(timeout=timeout_s) as c:
            r = c.get(f"{CATALOG_URL}/products/{product_id}")
        if r.status_code == 200:
            return r.json()
        # 404 u otro: tratamos como "no disponible" sin levantar excepcion.
        return None
    except httpx.HTTPError as exc:
        logger.warning("Catalog product %s fallo: %s", product_id, exc)
        return None


def catalog_update_rating(product_id: int, average: float, count: int,
                          token: str, correlation_id: str | None = None,
                          timeout_s: float = 2.0) -> bool:
    """Notifica a Catalog que el rating de un producto cambio.

    Se llama desde Commerce despues de que un admin aprueba una reseña.
    Catalog actualiza su RatingSummary cacheado para que la ficha publica
    refleje el nuevo promedio sin esperar a que expire el TTL del Cache-Aside.

    Devuelve True si Catalog confirmo 200 OK, False si fallo (no critico:
    Catalog se actualizara solo cuando expire el cache).
    """
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


# ═════════════════════════════════════════════════════════════════════════
# Inventory: variantes + reserve / confirm / release (SAGA)
# ═════════════════════════════════════════════════════════════════════════


def inventory_get_variant(variant_id: int, timeout_s: float = 2.0) -> dict | None:
    """Consulta el detalle de UNA variante en Inventory.

    Util cuando el cliente agrega un item al carrito y queremos validar
    stock + traer precio + nombre snapshot. Es la version individual de
    inventory_get_variants_by_ids.
    """
    try:
        with httpx.Client(timeout=timeout_s) as c:
            r = c.get(f"{INVENTORY_URL}/variants/{variant_id}")
        if r.status_code == 200:
            return r.json()
        return None
    except httpx.HTTPError as exc:
        logger.warning("Inventory variant %s fallo: %s", variant_id, exc)
        return None


def inventory_get_variants_by_ids(variant_ids: list[int], timeout_s: float = 2.0) -> dict[int, dict]:
    """Devuelve {variant_id: {price, cost, color, ...}} usando el endpoint
    batch `/variants/by-ids`.

    Es la version optimizada de inventory_get_variant: en vez de hacer N
    requests al consultar el carrito, hacemos UNA sola request que pide
    todas las variantes a la vez (separadas por coma en query string).

    Si Inventory falla devuelve {} (modo degradado: el caller seguira pero
    sin enriquecimiento de costos → COGS quedara en 0 para ese pedido).

    USO PRINCIPAL: dentro de la SAGA del checkout para snapshotear unit_cost
    en cada OrderItem y poder calcular COGS y margenes reales en el
    dashboard financiero.
    """
    if not variant_ids:
        return {}
    # CSV de ids para enviar en query string: ?ids=1,3,7
    ids_csv = ",".join(str(int(v)) for v in variant_ids)
    try:
        with httpx.Client(timeout=timeout_s) as c:
            r = c.get(f"{INVENTORY_URL}/variants/by-ids", params={"ids": ids_csv})
        if r.status_code != 200:
            return {}
        # Inventory devuelve lista; la indexamos por id para acceso O(1).
        return {row["id"]: row for row in r.json()}
    except httpx.HTTPError as exc:
        logger.warning("Inventory variants/by-ids fallo: %s", exc)
        return {}


def inventory_reserve(order_id: str, items: list[dict], token: str,
                      correlation_id: str | None = None, timeout_s: float = 5.0) -> dict:
    """Llama POST /reserve para reservar stock antes de cobrar.

    Es el PASO 1 de la SAGA del checkout. Inventory adquiere lock distribuido
    por variante + SELECT FOR UPDATE en MySQL y verifica que (stock -
    reserved_stock) >= quantity para cada item.

    Devuelve dict {status_code, body} para que el SAGA inspeccione:
      - 201 → reserva exitosa
      - 409 → algun item sin stock (body tiene `unavailable` con detalle)
      - otros → error inesperado

    Levanta ServiceUnavailable si Inventory no responde (timeout o conn refused).
    Esto es importante: el SAGA distingue "fallo de negocio" (409) de "fallo
    de infra" (ServiceUnavailable) y los maneja diferente.
    """
    try:
        with httpx.Client(timeout=timeout_s) as c:
            r = c.post(
                f"{INVENTORY_URL}/reserve",
                json={"order_id": order_id, "items": items, "ttl_seconds": 900},
                headers=_hdrs(token, correlation_id),
            )
        # Parseo defensivo: si Inventory devuelve algo que no es JSON, no
        # rompemos — devolvemos body={} y el SAGA lo trata como error.
        return {"status_code": r.status_code,
                "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else {}}
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        # Solo timeout y conn-error son ServiceUnavailable. Otros HTTPError
        # (ej. malformed response) los dejamos propagar como excepcion normal
        # que el FastAPI default 500-handler captura.
        raise ServiceUnavailable(f"Inventory no disponible: {exc}") from exc


def inventory_confirm(order_id: str, token: str, correlation_id: str | None = None,
                      timeout_s: float = 5.0) -> bool:
    """Llama POST /confirm/{order_id} para descontar el stock real.

    Es el PASO 3 de la SAGA (despues de cobrar exitosamente). Inventory:
      - Marca las StockReservation con status=CONFIRMED
      - Decrementa stock y reserved_stock de cada variante

    Devuelve True si exitoso, False si fallo. NO levanta excepcion porque
    en este punto la Order ya esta creada en PAID — un fallo aqui es un
    caso raro que registramos en audit_log pero no rompe el flujo.
    """
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
    """Llama POST /release para LIBERAR el stock reservado (COMPENSACION).

    Se usa cuando un paso posterior de la SAGA falla (pago rechazado,
    pasarela caida, CB abierto) y necesitamos deshacer la reserva del
    paso 1. Inventory:
      - Marca las StockReservation con status=RELEASED
      - Decrementa solo reserved_stock (stock NO baja porque nunca subio)

    `reason` se guarda en el motivo del movimiento para auditoria
    (ej. "payment_rejected", "payment_circuit_open").
    """
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


# ═════════════════════════════════════════════════════════════════════════
# Payment: cargo a la pasarela
# ═════════════════════════════════════════════════════════════════════════


def payment_charge(order_id: str, amount: float, currency: str, token: str,
                   card_token: str | None = None, correlation_id: str | None = None,
                   timeout_s: float = 8.0) -> dict:
    """Llama POST /payments para autorizar el cobro.

    Es el PASO 2 de la SAGA. Payment internamente:
      - Verifica el Circuit Breaker (si OPEN, devuelve 503 sin tocar pasarela)
      - Llama a POST /charge del payment-mock
      - Aplica reintentos exponenciales si hay errores transitorios

    Devuelve dict {status_code, body}:
      - 200 con body.status=APPROVED → pago exitoso
      - 200 con body.status=REJECTED → pago rechazado (negocio)
      - 503 → Circuit Breaker abierto (infra protectora)
      - otros → error inesperado

    Timeout mas alto (8s) que otras llamadas porque la pasarela puede
    tomarse su tiempo en autorizar. Levanta ServiceUnavailable si Payment
    cae completamente.
    """
    try:
        with httpx.Client(timeout=timeout_s) as c:
            r = c.post(
                f"{PAYMENT_URL}/payments",
                json={"order_id": order_id, "amount": amount, "currency": currency,
                      "card_token": card_token},
                headers=_hdrs(token, correlation_id),
            )
        # Parseo defensivo del body — si la pasarela devuelve texto plano
        # (raro pero posible), lo encapsulamos en {raw: ...}.
        body: Any = {}
        try:
            body = r.json()
        except Exception:  # noqa: BLE001
            body = {"raw": r.text}
        return {"status_code": r.status_code, "body": body}
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        raise ServiceUnavailable(f"Payment no disponible: {exc}") from exc


# ═════════════════════════════════════════════════════════════════════════
# Auth: lookup de customer (para admin que consulta detalle de pedido)
# ═════════════════════════════════════════════════════════════════════════


def auth_get_customer(customer_id: int, token: str, timeout_s: float = 2.0) -> dict | None:
    """Consulta el perfil de un customer en Auth Service.

    Lo usa el panel admin para mostrar nombre/email del cliente en el
    detalle de un pedido (sin guardar redundantemente esos datos en
    commerce_db). Best-effort: si Auth cae, el admin ve solo el user_id.
    """
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
