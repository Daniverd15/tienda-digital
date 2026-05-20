"""POST /checkout - punto de entrada de la SAGA orquestada sincrona.

Aplica Idempotency Key: si se reenvia el mismo header, NO crea otra orden.
"""
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import current_user_id, get_correlation_id, get_current_user_token
from app.models import Cart, Order, OrderItem
from app.schemas import CheckoutRequest
from app.services.checkout_saga import execute_checkout
from app.services.http_clients import inventory_get_variants_by_ids


router = APIRouter(tags=["Checkout"])


def _new_order_code() -> str:
    ts = datetime.now().strftime("%Y%m%d")
    return f"ORD-{ts}-{uuid4().hex[:8].upper()}"


@router.post("/checkout", status_code=status.HTTP_201_CREATED)
def checkout(
    payload: CheckoutRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
    token: str = Depends(get_current_user_token),
    correlation_id: str = Depends(get_correlation_id),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    cart = (
        db.query(Cart)
        .filter(Cart.user_id == user_id, Cart.status == "open")
        .first()
    )
    if not cart or not cart.items:
        raise HTTPException(400, "Tu carrito esta vacio.")

    # Idempotency: si llega con la misma key, devolvemos el resultado existente
    if idempotency_key:
        existing = (
            db.query(Order)
            .filter(Order.user_id == user_id, Order.order_code.like(f"%{idempotency_key[:8].upper()}"))
            .first()
        )
        if existing:
            return {
                "order_id": existing.id, "order_code": existing.order_code,
                "status": existing.status, "payment_status": existing.payment_status,
                "total": float(existing.total),
                "message": "Orden ya creada con esta Idempotency-Key.",
            }

    # 1. Calcular totales (snapshot del carrito)
    subtotal = sum(Decimal(str(i.unit_price)) * i.quantity for i in cart.items)
    # En checkout de cliente no se aceptan ajustes de precio enviados desde el
    # navegador. Descuentos y costos adicionales pertenecen a flujo admin/backoffice.
    additional = Decimal("0")
    discount = Decimal("0")
    total = max(Decimal("0"), subtotal + additional - discount)

    # 2. Crear orden CREATED. El order_code SIEMPRE usa uuid4 para evitar
    # colisiones cuando la misma Idempotency-Key llega de usuarios distintos
    # (la idempotencia es por (user_id, idempotency_key), no por order_code).
    code = _new_order_code()
    order = Order(
        order_code=code, user_id=user_id, status="CREATED", payment_status="PENDING",
        subtotal=subtotal, additional_costs=additional, discount=discount, total=total,
        currency="COP",
        delivery_name=payload.delivery_name, delivery_address=payload.delivery_address,
        delivery_city=payload.delivery_city, billing_document=payload.billing_document,
        contact_phone=payload.contact_phone, contact_email=payload.contact_email,
        correlation_id=correlation_id,
    )
    db.add(order)
    db.flush()

    # Snapshot del costo unitario desde Inventory para calculo posterior de COGS
    # y margenes en el dashboard financiero. Una sola request batch para todos.
    variant_ids = list({i.variant_id for i in cart.items})
    cost_map = inventory_get_variants_by_ids(variant_ids)

    for it in cart.items:
        info = cost_map.get(it.variant_id, {})
        unit_cost = Decimal(str(info.get("cost") or 0))
        db.add(OrderItem(
            order_id=order.id, variant_id=it.variant_id, product_id=it.product_id,
            product_name=it.product_name, variant_description=it.variant_description,
            image_url=it.image_url, quantity=it.quantity,
            unit_price=Decimal(str(it.unit_price)),
            unit_cost=unit_cost,
            total=Decimal(str(it.unit_price)) * it.quantity,
        ))
    db.commit()
    db.refresh(order)

    # 3. Ejecutar SAGA (reserve -> charge -> confirm/release + notificar)
    result = execute_checkout(
        db=db, cart=cart, order=order, user_id=user_id,
        token=token, correlation_id=correlation_id, card_token=payload.card_token,
    )
    return result
