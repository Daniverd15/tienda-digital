from datetime import datetime
from decimal import Decimal
from random import randint

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.api.cart import get_open_cart
from app.api.dependencies import get_current_user, require_admin, require_customer
from app.core.database import get_db
from app.models import (
    Cart,
    CartItem,
    InventoryMovement,
    Notification,
    Order,
    OrderItem,
    Payment,
    ProductVariant,
    User,
)
from app.schemas import ApiMessage, CheckoutIn, OrderCreate, OrderStatusUpdate, PaymentSimulateIn
from app.services.audit_service import add_audit_log


router = APIRouter(tags=["Checkout y pedidos"])


def calculate_cart_totals(cart, discount: Decimal = Decimal("0"), additional_costs: Decimal = Decimal("0")) -> dict:
    subtotal = sum(Decimal(item.unit_price) * item.quantity for item in cart.items)
    discount = max(Decimal(discount or 0), Decimal("0"))
    additional_costs = max(Decimal(additional_costs or 0), Decimal("0"))
    total = subtotal + additional_costs - discount
    if total < 0:
        total = Decimal("0")
    return {
        "subtotal": subtotal,
        "additional_costs": additional_costs,
        "discount": discount,
        "total": total,
    }


def serialize_order(order: Order) -> dict:
    return {
        "id": order.id,
        "order_code": order.order_code,
        "status": order.status,
        "payment_status": order.payment_status,
        "subtotal": float(order.subtotal),
        "additional_costs": float(order.additional_costs),
        "discount": float(order.discount),
        "total": float(order.total),
        "delivery_name": order.delivery_name,
        "delivery_address": order.delivery_address,
        "delivery_city": order.delivery_city,
        "billing_document": order.billing_document,
        "contact_phone": order.contact_phone,
        "contact_email": order.contact_email,
        "created_at": order.created_at,
        "items": [
            {
                "id": item.id,
                "variant_id": item.variant_id,
                "product_id": item.variant.product_id if item.variant else None,
                "product_name": item.product_name,
                "variant_description": item.variant_description,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "total": float(item.total),
            }
            for item in order.items
        ],
        "payments": [
            {
                "id": payment.id,
                "provider": payment.provider,
                "transaction_reference": payment.transaction_reference,
                "status": payment.status,
                "amount": float(payment.amount),
                "response_message": payment.response_message,
                "created_at": payment.created_at,
            }
            for payment in order.payments
        ],
    }


@router.post("/checkout")
def checkout(payload: CheckoutIn, current_user: User = Depends(require_customer), db: Session = Depends(get_db)):
    cart = get_open_cart(db, current_user.id)
    if not cart.items:
        raise HTTPException(status_code=409, detail="El carrito esta vacio.")
    stock_errors = [
        {"variant_id": item.variant_id, "requested": item.quantity, "available": item.variant.stock}
        for item in cart.items
        if item.quantity > item.variant.stock
    ]
    if stock_errors:
        raise HTTPException(status_code=409, detail={"message": "Stock insuficiente.", "errors": stock_errors})
    totals = calculate_cart_totals(cart, payload.discount, payload.additional_costs)
    return {
        "items": [
            {
                "product_name": item.variant.product.name,
                "variant_id": item.variant_id,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "total": float(Decimal(item.unit_price) * item.quantity),
            }
            for item in cart.items
        ],
        "subtotal": float(totals["subtotal"]),
        "additional_costs": float(totals["additional_costs"]),
        "discount": float(totals["discount"]),
        "total": float(totals["total"]),
    }


@router.post("/payments/simulate")
def simulate_payment(payload: PaymentSimulateIn):
    status = payload.requested_status
    messages = {
        "aprobado": "Pago aprobado por pasarela simulada.",
        "rechazado": "Pago rechazado por fondos insuficientes simulados.",
        "pendiente": "Pago pendiente de confirmacion simulada.",
    }
    return {
        "provider": "SimuladorLocal",
        "transaction_reference": f"SIM-{datetime.utcnow():%Y%m%d%H%M%S}-{randint(1000, 9999)}",
        "status": status,
        "amount": float(payload.amount),
        "response_message": messages[status],
    }


@router.post("/orders", status_code=201)
def create_order(payload: OrderCreate, current_user: User = Depends(require_customer), db: Session = Depends(get_db)):
    get_open_cart(db, current_user.id)
    cart = (
        db.query(Cart)
        .options(joinedload(Cart.items).joinedload(CartItem.variant).joinedload(ProductVariant.product))
        .filter_by(user_id=current_user.id, status="open")
        .first()
    )
    if not cart or not cart.items:
        raise HTTPException(status_code=409, detail="El carrito esta vacio.")
    totals = calculate_cart_totals(cart, payload.discount, payload.additional_costs)
    try:
        if payload.payment_status == "aprobado":
            for item in cart.items:
                if item.quantity > item.variant.stock:
                    raise HTTPException(status_code=409, detail="Stock insuficiente al confirmar el pago.")
                item.variant.stock -= item.quantity
                db.add(
                    InventoryMovement(
                        variant_id=item.variant_id,
                        movement_type="salida",
                        quantity=item.quantity,
                        reason="Venta aprobada",
                        user_id=current_user.id,
                    )
                )
        status = {
            "aprobado": "preparacion",
            "pendiente": "pendiente_pago",
            "rechazado": "rechazado",
        }[payload.payment_status]
        order = Order(
            order_code=f"TD-{datetime.utcnow():%Y%m%d%H%M%S}-{current_user.id}-{randint(100, 999)}",
            user_id=current_user.id,
            status=status,
            payment_status=payload.payment_status,
            subtotal=totals["subtotal"],
            additional_costs=totals["additional_costs"],
            discount=totals["discount"],
            total=totals["total"],
            delivery_name=payload.delivery_name,
            delivery_address=payload.delivery_address,
            delivery_city=payload.delivery_city,
            billing_document=payload.billing_document,
            contact_phone=payload.contact_phone,
            contact_email=payload.contact_email,
        )
        db.add(order)
        db.flush()
        for item in cart.items:
            variant_description = " / ".join(
                part for part in [item.variant.color, item.variant.size, item.variant.custom_attribute] if part
            ) or item.variant.sku
            db.add(
                OrderItem(
                    order_id=order.id,
                    variant_id=item.variant_id,
                    product_name=item.variant.product.name,
                    variant_description=variant_description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total=Decimal(item.unit_price) * item.quantity,
                )
            )
        db.add(
            Payment(
                order_id=order.id,
                provider="SimuladorLocal",
                transaction_reference=payload.transaction_reference,
                status=payload.payment_status,
                amount=totals["total"],
                response_message=payload.response_message or "Respuesta registrada.",
            )
        )
        db.add(
            Notification(
                user_id=current_user.id,
                order_id=order.id,
                title="Pedido creado",
                message=f"Tu pedido {order.order_code} quedo en estado {status}.",
            )
        )
        cart.status = "checked_out"
        add_audit_log(
            db,
            user_id=current_user.id,
            action="create_order",
            entity="orders",
            entity_id=order.id,
            new_value={"payment_status": payload.payment_status, "total": str(totals["total"])},
        )
        db.commit()
        order = (
            db.query(Order)
            .options(joinedload(Order.items), joinedload(Order.payments))
            .filter(Order.id == order.id)
            .first()
        )
        return serialize_order(order)
    except HTTPException:
        db.rollback()
        raise


@router.get("/orders/my")
def my_orders(current_user: User = Depends(require_customer), db: Session = Depends(get_db)):
    orders = (
        db.query(Order)
        .options(joinedload(Order.items), joinedload(Order.payments))
        .filter(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
        .all()
    )
    return [serialize_order(order) for order in orders]


@router.get("/orders/{order_id}")
def order_detail(order_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = (
        db.query(Order)
        .options(joinedload(Order.items), joinedload(Order.payments))
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")
    if current_user.role != "admin" and order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No puedes ver pedidos de otros usuarios.")
    return serialize_order(order)


@router.get("/notifications")
def my_notifications(current_user: User = Depends(require_customer), db: Session = Depends(get_db)):
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return [
        {
            "id": notification.id,
            "order_id": notification.order_id,
            "title": notification.title,
            "message": notification.message,
            "read": notification.read,
            "created_at": notification.created_at,
        }
        for notification in notifications
    ]


@router.put("/notifications/{notification_id}/read", response_model=ApiMessage)
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notificacion no encontrada.")
    notification.read = True
    db.commit()
    return ApiMessage(message="Notificacion marcada como leida.")


@router.get("/admin/orders")
def admin_orders(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    orders = (
        db.query(Order)
        .options(joinedload(Order.items), joinedload(Order.payments))
        .order_by(Order.created_at.desc())
        .all()
    )
    return [serialize_order(order) for order in orders]


@router.put("/admin/orders/{order_id}/status")
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    valid_statuses = {"pendiente_pago", "preparacion", "enviado", "entregado", "cancelado", "rechazado"}
    if payload.status not in valid_statuses:
        raise HTTPException(status_code=422, detail="Estado de pedido no valido.")
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")
    if payload.status in {"preparacion", "enviado", "entregado"} and order.payment_status != "aprobado":
        raise HTTPException(status_code=409, detail="Un pedido no puede avanzar sin pago aprobado.")
    previous = {"status": order.status}
    order.status = payload.status
    db.add(
        Notification(
            user_id=order.user_id,
            order_id=order.id,
            title="Estado de pedido actualizado",
            message=f"Tu pedido {order.order_code} ahora esta en estado {order.status}.",
        )
    )
    add_audit_log(
        db,
        user_id=admin.id,
        action="update_order_status",
        entity="orders",
        entity_id=order.id,
        previous_value=previous,
        new_value={"status": order.status},
    )
    db.commit()
    db.refresh(order)
    return serialize_order(order)
