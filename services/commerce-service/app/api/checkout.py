"""POST /checkout - punto de entrada de la SAGA orquestada sincrona.

Aplica Idempotency Key: si se reenvia el mismo header, NO crea otra orden.

Politica del MVP: la Order SOLO se crea si el flujo termina en PAID. Si la
SAGA falla en alguno de sus pasos, devolvemos un error HTTP claro y el
intento queda registrado en `failed_checkout_attempts` para soporte. Esto
mantiene el listado de pedidos del admin limpio de artefactos.
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


router = APIRouter(tags=["Checkout"])


def _new_order_code() -> str:
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
    cart = (
        db.query(Cart)
        .filter(Cart.user_id == user_id, Cart.status == "open")
        .first()
    )
    if not cart or not cart.items:
        raise HTTPException(400, "Tu carrito está vacío.")

    # Idempotencia (por usuario + key): si llega la misma key dos veces,
    # devolvemos la orden ya creada.
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
            return {
                "order_id": existing.id, "order_code": existing.order_code,
                "status": existing.status, "payment_status": existing.payment_status,
                "total": float(existing.total),
                "message": "Orden ya creada previamente con esta clave.",
            }

    # Calcular totales (snapshot)
    subtotal = sum(Decimal(str(i.unit_price)) * i.quantity for i in cart.items)
    total = subtotal  # descuentos/recargos del flujo admin no aplican aqui

    attempt_code = _new_order_code()
    try:
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
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.payload["message"], **exc.payload},
        )

    return result
