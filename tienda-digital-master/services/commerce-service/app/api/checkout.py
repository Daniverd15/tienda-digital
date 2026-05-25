"""POST /checkout - punto de entrada de la SAGA orquestada sincrona.

================================================================================
PROPOSITO
================================================================================
Es el endpoint HTTP que el frontend invoca cuando el cliente confirma el pago.
Su trabajo es minimo:
  1. Validar que el carrito tenga items.
  2. Aplicar idempotencia (si llega la misma request dos veces, no duplicar).
  3. Calcular totales.
  4. Delegar al orquestador SAGA (`checkout_saga.execute_checkout`).
  5. Traducir el resultado (exito o CheckoutError) a HTTP.

La logica de coordinacion entre microservicios vive en `checkout_saga.py`,
NO aqui. Este modulo es solo el adaptador HTTP.

================================================================================
IDEMPOTENCIA
================================================================================
Si el cliente hace doble clic o el navegador reintenta la request (mala
conexion), llegaria la misma POST /checkout dos veces. Sin proteccion,
se cobraria dos veces y se descontaria stock doble.

Solucion: el frontend envia un header `Idempotency-Key` con un UUID por
intento. Si llega una request con la misma key + mismo user_id, devolvemos
la Order ya creada en vez de crear una nueva.

Convencion: el frontend genera la key con `${Date.now()}-${random}` ANTES
de mostrar el modal de "procesando". Si el usuario refresca o reintenta,
usa la misma key.

================================================================================
POLITICA DEL MVP
================================================================================
La Order SOLO se crea si la SAGA termina en PAID. Si falla en cualquier
paso (sin stock, pago rechazado, pasarela caida), devolvemos un error HTTP
claro y el intento queda registrado en `failed_checkout_attempts` para
auditoria/soporte. Esto mantiene el panel admin limpio de pedidos fantasma.
"""
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import current_user_id, get_correlation_id, get_current_user_token
from app.models import Cart, Order
from app.schemas import CheckoutRequest
from app.services.checkout_saga import CheckoutError, execute_checkout


# Router de FastAPI. Tag "Checkout" agrupa este endpoint en /docs (Swagger UI).
router = APIRouter(tags=["Checkout"])


def _new_order_code() -> str:
    """Genera un order_code unico estilo `ORD-20260520-XXXXXXXX`.

    Formato: `ORD-` + fecha (YYYYMMDD) + 8 chars hex aleatorios del uuid4.
    La fecha facilita ordenar/buscar pedidos en logs. El uuid garantiza
    unicidad incluso si dos checkouts ocurren en el mismo segundo.

    Antes usabamos los primeros 8 chars de la Idempotency-Key, pero eso
    causaba colisiones cuando dos usuarios distintos enviaban la misma key
    (raro pero posible). Ahora siempre uuid4 → cero colisiones.
    """
    ts = datetime.now().strftime("%Y%m%d")
    return f"ORD-{ts}-{uuid4().hex[:8].upper()}"


@router.post("/checkout")
def checkout(
    payload: CheckoutRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
    token: str = Depends(get_current_user_token),
    correlation_id: str = Depends(get_correlation_id),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Ejecuta el checkout completo coordinando Inventory + Payment + Commerce.

    Headers:
        Idempotency-Key (opcional): UUID que protege contra duplicacion si
                                    se reintenta la misma request.

    Body (CheckoutRequest):
        delivery_name, delivery_address, delivery_city, billing_document,
        contact_phone, contact_email, card_token (opcional)

    Respuestas:
        200/201 → {order_id, order_code, status: "PAID", total} (exito)
        400     → carrito vacio
        402     → pago rechazado por la pasarela
        409     → stock insuficiente
        503     → pasarela no disponible (CB abierto o Inventory caido)
    """
    # ─── 1. Validar que el cliente tenga un carrito abierto con items ────
    # Solo hay UN carrito "open" por usuario (constraint logica).
    # Si no hay carrito o esta vacio, no tiene sentido iniciar checkout.
    cart = (
        db.query(Cart)
        .filter(Cart.user_id == user_id, Cart.status == "open")
        .first()
    )
    if not cart or not cart.items:
        raise HTTPException(400, "Tu carrito está vacío.")

    # ─── 2. Idempotencia: si la misma request llego antes, devolver el resultado
    # ya calculado en vez de reprocesar.
    # Buscamos por (user_id, correlation_id). El correlation_id se deriva
    # del Idempotency-Key indirectamente: el gateway lo asigna en base al
    # header si esta presente.
    if idempotency_key:
        existing = (
            db.query(Order)
            .filter(
                Order.user_id == user_id,
                Order.correlation_id == correlation_id,
            )
            .first()
        )
        if existing:
            # Idempotente: devolvemos la Order ya creada (mismo response).
            return {
                "order_id": existing.id, "order_code": existing.order_code,
                "status": existing.status, "payment_status": existing.payment_status,
                "total": float(existing.total),
                "message": "Orden ya creada previamente con esta clave.",
            }

    # ─── 3. Calcular totales tomando snapshot del carrito ────────────────
    # Usamos Decimal para evitar errores de coma flotante en operaciones
    # monetarias. Convertimos al final a float para el SAGA.
    # En este punto no aplicamos descuentos/recargos: el admin podria
    # configurarlos en /admin pero la version cliente del checkout no los
    # acepta (evita manipulacion del precio desde el navegador).
    subtotal = sum(Decimal(str(i.unit_price)) * i.quantity for i in cart.items)
    total = subtotal

    # ─── 4. Generar codigo unico para la Order y ejecutar SAGA ───────────
    attempt_code = _new_order_code()
    try:
        # El SAGA hace TODO el trabajo pesado:
        # - reserve en Inventory (con lock + SELECT FOR UPDATE)
        # - charge en Payment (con CB + reintentos)
        # - confirm en Inventory (descuenta stock real)
        # - crea Order + OrderItems + audit + notificacion
        result = execute_checkout(
            db=db, cart=cart, user_id=user_id, token=token,
            correlation_id=correlation_id,
            delivery_name=payload.delivery_name,
            delivery_address=payload.delivery_address,
            delivery_city=payload.delivery_city,
            billing_document=payload.billing_document,
            contact_phone=payload.contact_phone,
            contact_email=payload.contact_email,
            card_token=payload.card_token,
            attempt_code=attempt_code,
            subtotal=float(subtotal), total=float(total),
        )
    except CheckoutError as exc:
        # ─── 5. Traducir CheckoutError a JSONResponse con HTTP correcto ──
        # CheckoutError lleva status_code (409/402/503/502) y payload
        # {code, message, ...}. El frontend lee `code` para mapear a icono
        # y mensaje especifico (out_of_stock, payment_rejected, etc.).
        # Usamos JSONResponse en vez de HTTPException porque queremos que el
        # body incluya MAS campos que solo `detail` (como `code` y `unavailable`).
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.payload["message"], **exc.payload},
        )

    # Caso exitoso: el SAGA devolvio CheckoutOK. FastAPI lo serializa como JSON.
    return result
