"""Endpoints de pedidos del cliente.

================================================================================
PROPOSITO
================================================================================
Permite al cliente consultar SU historial de pedidos y el detalle de uno
especifico. Es el lado cliente del RF-06 del SRS (gestion de pedidos).

Endpoints:
  GET /orders/mine       → listado de pedidos del usuario autenticado
  GET /orders/{order_id} → detalle completo de UN pedido propio (con history)

================================================================================
SEGURIDAD
================================================================================
Ambos endpoints filtran por user_id del JWT para evitar que un cliente
consulte pedidos ajenos (IDOR). Si pide un order_id que no es suyo,
devuelven 404 (no 403) para no revelar si el id existe.

El admin tiene endpoints separados en /admin/orders/* (en api/admin.py)
con permisos diferentes y vista completa.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import current_user_id
from app.models import Order


router = APIRouter(prefix="/orders", tags=["Pedidos del cliente"])


def _serialize_order(order: Order, include_history: bool = True) -> dict:
    """Convierte una Order (ORM) a dict listo para JSON.

    Incluye los items embebidos (siempre) y el timeline de transiciones
    de estado (opcional, default True). El admin tambien usa esta funcion
    para el detalle (con history) y el listado (sin history).
    """
    # Items: snapshot del pedido. unit_price y total son los del momento
    # del checkout, NO los actuales en Inventory (consistencia historica).
    items = [{
        "id": i.id, "variant_id": i.variant_id, "product_id": i.product_id,
        "product_name": i.product_name, "variant_description": i.variant_description,
        "image_url": i.image_url, "quantity": i.quantity,
        "unit_price": float(i.unit_price), "total": float(i.total),
    } for i in order.items]

    data = {
        "id": order.id, "order_code": order.order_code, "user_id": order.user_id,
        "status": order.status, "payment_status": order.payment_status,
        "payment_reference": order.payment_reference,
        "payment_message": order.payment_message,
        # Totales: Decimal → float para JSON.
        "subtotal": float(order.subtotal),
        "additional_costs": float(order.additional_costs),
        "discount": float(order.discount), "total": float(order.total),
        "currency": order.currency,
        # Datos de entrega: snapshot del checkout.
        "delivery_name": order.delivery_name, "delivery_address": order.delivery_address,
        "delivery_city": order.delivery_city, "billing_document": order.billing_document,
        "contact_phone": order.contact_phone, "contact_email": order.contact_email,
        # Timestamps: ISO format para que el frontend los pueda parsear.
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
        "items": items,
    }
    if include_history:
        # Timeline de transiciones: PAID → EN_PREPARACION → ENVIADO → ENTREGADO.
        # Cada entrada lleva quien lo cambio (admin_id) y cuando.
        # El frontend lo usa para renderizar el timeline visual del pedido.
        data["history"] = [
            {
                "from_status": h.from_status, "to_status": h.to_status,
                "changed_by": h.changed_by, "notes": h.notes,
                "changed_at": h.changed_at.isoformat(),
            }
            for h in order.history
        ]
    return data


@router.get("/mine")
def list_my_orders(
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    """Lista todos los pedidos del usuario autenticado (mas recientes primero).

    No incluye history para reducir el tamaño del response (el frontend
    solo necesita el estado actual para mostrar la lista).

    joinedload de items previene N+1 queries: una sola query SQL trae las
    Orders junto con todos sus OrderItems.
    """
    rows = (
        db.query(Order)
        .options(joinedload(Order.items), joinedload(Order.history))
        .filter(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .all()
    )
    return [_serialize_order(o, include_history=False) for o in rows]


@router.get("/{order_id}")
def get_my_order(
    order_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    """Detalle completo de un pedido del usuario, incluyendo history.

    El filtro `Order.user_id == user_id` IMPIDE que un cliente vea pedidos
    ajenos (defensa contra IDOR). Si el order_id no existe O no es del
    usuario → 404 (no diferenciamos para no leak info).
    """
    order = (
        db.query(Order)
        .options(joinedload(Order.items), joinedload(Order.history))
        .filter(Order.id == order_id, Order.user_id == user_id)
        .first()
    )
    if not order:
        raise HTTPException(404, "Pedido no encontrado.")
    return _serialize_order(order, include_history=True)
