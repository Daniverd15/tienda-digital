"""Endpoints de pedidos del cliente."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import current_user_id
from app.models import Order


router = APIRouter(prefix="/orders", tags=["Pedidos del cliente"])


def _serialize_order(order: Order, include_history: bool = True) -> dict:
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
        "subtotal": float(order.subtotal),
        "additional_costs": float(order.additional_costs),
        "discount": float(order.discount), "total": float(order.total),
        "currency": order.currency,
        "delivery_name": order.delivery_name, "delivery_address": order.delivery_address,
        "delivery_city": order.delivery_city, "billing_document": order.billing_document,
        "contact_phone": order.contact_phone, "contact_email": order.contact_email,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
        "items": items,
    }
    if include_history:
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
    order = (
        db.query(Order)
        .options(joinedload(Order.items), joinedload(Order.history))
        .filter(Order.id == order_id, Order.user_id == user_id)
        .first()
    )
    if not order:
        raise HTTPException(404, "Pedido no encontrado.")
    return _serialize_order(order, include_history=True)
