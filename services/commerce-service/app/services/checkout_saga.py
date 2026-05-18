"""Orquestador de la SAGA orquestada sincrona del checkout.

Materializa el diagrama 11.0 del informe Fase 1:
- Commerce crea Order(CREATED)
- Llama a Inventory para reservar (REST con timeout)
- Llama a Payment para autorizar (REST con timeout)
- Segun resultado: confirma o libera la reserva (compensacion HTTP)
- Marca el estado final de la orden y registra historia + auditoria
- Notifica al cliente via SMTP (Mailhog)
"""
import logging
from decimal import Decimal
from typing import TypedDict

from sqlalchemy.orm import Session

from app.models import (
    Cart,
    Notification,
    Order,
    OrderAuditLog,
    OrderItem,
    OrderStatusHistory,
)
from app.services.http_clients import (
    ServiceUnavailable,
    inventory_confirm,
    inventory_release,
    inventory_reserve,
    payment_charge,
)
from app.services.mailer import send_email

logger = logging.getLogger(__name__)


class CheckoutResult(TypedDict):
    order_id: int
    order_code: str
    status: str
    payment_status: str
    total: float
    message: str


def _transition(db: Session, order: Order, new_status: str, changed_by: int | None,
                notes: str | None = None) -> None:
    prev = order.status
    order.status = new_status
    db.add(OrderStatusHistory(
        order_id=order.id, from_status=prev, to_status=new_status,
        changed_by=changed_by, notes=notes,
    ))


def _audit(db: Session, order_id: int | None, action: str, performed_by: int | None,
           details: str, correlation_id: str | None) -> None:
    db.add(OrderAuditLog(
        order_id=order_id, action=action, performed_by=performed_by,
        details=details[:2000], correlation_id=correlation_id,
    ))


def _notify_user(db: Session, user_id: int, order_id: int | None, title: str, message: str,
                 email: str | None = None) -> None:
    db.add(Notification(user_id=user_id, order_id=order_id, title=title, message=message))
    if email:
        send_email(email, title, message)


def execute_checkout(
    db: Session,
    cart: Cart,
    order: Order,
    user_id: int,
    token: str,
    correlation_id: str,
    card_token: str | None,
) -> CheckoutResult:
    """Ejecuta la SAGA orquestada sincrona. Asume que la orden ya esta creada en CREATED.

    Itera por los items del carrito, reserva en Inventory, autoriza el pago,
    confirma o libera segun resultado. Persiste TODO en la misma transaccion
    de Commerce y deja la orden en su estado final.
    """
    items_payload = [{"variant_id": i.variant_id, "quantity": i.quantity} for i in cart.items]

    # 1. RESERVAR
    try:
        resp = inventory_reserve(order.order_code, items_payload, token, correlation_id)
    except ServiceUnavailable as exc:
        logger.error("Reserve fallo: %s", exc)
        _transition(db, order, "SIN_STOCK", user_id, "Inventory no disponible")
        _audit(db, order.id, "checkout_reserve_unavailable", user_id, str(exc), correlation_id)
        _notify_user(db, user_id, order.id, "No pudimos confirmar tu pedido",
                     f"Servicio de inventario temporalmente no disponible. Reintenta en unos minutos."
                     f"\nCodigo: {order.order_code}",
                     email=order.contact_email)
        db.commit()
        return CheckoutResult(order_id=order.id, order_code=order.order_code,
                              status=order.status, payment_status=order.payment_status,
                              total=float(order.total),
                              message="Inventario no disponible. Reintenta en unos minutos.")

    if resp["status_code"] == 409:
        detail = resp["body"].get("detail") if isinstance(resp["body"], dict) else None
        _transition(db, order, "SIN_STOCK", user_id, f"Reserva fallo: {detail}")
        _audit(db, order.id, "checkout_no_stock", user_id, str(detail), correlation_id)
        _notify_user(db, user_id, order.id, "Producto sin stock",
                     f"Lo sentimos, alguna(s) variantes de tu pedido {order.order_code} ya no tienen stock.",
                     email=order.contact_email)
        db.commit()
        return CheckoutResult(order_id=order.id, order_code=order.order_code,
                              status="SIN_STOCK", payment_status=order.payment_status,
                              total=float(order.total),
                              message="No hay stock suficiente para uno o mas productos.")
    if resp["status_code"] not in (200, 201):
        _transition(db, order, "SIN_STOCK", user_id, f"Reserve respondio {resp['status_code']}")
        _audit(db, order.id, "checkout_reserve_error", user_id, str(resp), correlation_id)
        db.commit()
        return CheckoutResult(order_id=order.id, order_code=order.order_code,
                              status="SIN_STOCK", payment_status=order.payment_status,
                              total=float(order.total),
                              message="Error al reservar inventario.")

    _transition(db, order, "AWAITING_PAYMENT", user_id, "Stock reservado")

    # 2. PAGAR
    try:
        pay = payment_charge(order.order_code, float(order.total), order.currency,
                             token, card_token=card_token, correlation_id=correlation_id)
    except ServiceUnavailable as exc:
        logger.warning("Payment no disponible: %s", exc)
        order.payment_status = "PENDING"
        order.payment_message = "Pasarela no disponible; reintenta mas tarde."
        _transition(db, order, "PAGO_PENDIENTE", user_id, "Payment service no respondio")
        _audit(db, order.id, "payment_unavailable", user_id, str(exc), correlation_id)
        _notify_user(db, user_id, order.id, "Pago pendiente",
                     f"Tu pedido {order.order_code} quedo en PAGO PENDIENTE; reintenta en unos minutos.",
                     email=order.contact_email)
        db.commit()
        return CheckoutResult(order_id=order.id, order_code=order.order_code,
                              status="PAGO_PENDIENTE", payment_status="PENDING",
                              total=float(order.total),
                              message="Servicio de pagos no disponible.")

    body = pay["body"] if isinstance(pay["body"], dict) else {}
    pay_status = body.get("status", "FAILED")
    order.payment_id = body.get("payment_id")
    order.payment_reference = body.get("transaction_reference")
    order.payment_message = (body.get("message") or "")[:250]

    if pay_status == "APPROVED":
        # 3a. CONFIRMAR EN INVENTORY
        ok = inventory_confirm(order.order_code, token, correlation_id)
        if not ok:
            # caso raro: pago aprobado pero confirm fallo. Mantenemos PAID; el scheduler
            # de inventory liberara la reserva al expirar y un admin debera revisar.
            _audit(db, order.id, "confirm_after_paid_failed", user_id,
                   "Inventory confirm fallo; reserva vencera y stock no bajara correctamente.",
                   correlation_id)
        order.payment_status = "APPROVED"
        _transition(db, order, "PAID", user_id, "Pago aprobado y stock descontado")
        _audit(db, order.id, "payment_approved", user_id,
               f"ref={order.payment_reference}", correlation_id)
        _notify_user(db, user_id, order.id, "Compra exitosa",
                     f"Tu pedido {order.order_code} fue pagado con exito.\n"
                     f"Total: {float(order.total):,.0f} {order.currency}\n"
                     f"Te avisaremos cuando se prepare y se despache.",
                     email=order.contact_email)
        cart.status = "checked_out"
        db.commit()
        return CheckoutResult(order_id=order.id, order_code=order.order_code,
                              status="PAID", payment_status="APPROVED",
                              total=float(order.total),
                              message="Pago aprobado. Compra confirmada.")

    if pay_status == "REJECTED":
        # 3b. LIBERAR RESERVA (compensacion)
        inventory_release(order.order_code, "payment_rejected", token, correlation_id)
        order.payment_status = "REJECTED"
        _transition(db, order, "PAGO_RECHAZADO", user_id, "Pago rechazado por la pasarela")
        _audit(db, order.id, "payment_rejected", user_id,
               order.payment_message or "", correlation_id)
        _notify_user(db, user_id, order.id, "Pago rechazado",
                     f"Tu pago para el pedido {order.order_code} fue rechazado por la pasarela.\n"
                     f"Razon: {order.payment_message}. Puedes reintentar con otro metodo.",
                     email=order.contact_email)
        db.commit()
        return CheckoutResult(order_id=order.id, order_code=order.order_code,
                              status="PAGO_RECHAZADO", payment_status="REJECTED",
                              total=float(order.total), message="Pago rechazado.")

    # PENDING o FAILED: NO liberamos reserva todavia (espera de scheduler / reconciliacion)
    order.payment_status = pay_status
    _transition(db, order, "PAGO_PENDIENTE", user_id, f"Pago {pay_status}")
    _audit(db, order.id, "payment_pending_or_failed", user_id, str(body), correlation_id)
    _notify_user(db, user_id, order.id, "Pago pendiente",
                 f"Tu pago para el pedido {order.order_code} quedo en estado {pay_status}.\n"
                 f"Te avisaremos cuando se resuelva.",
                 email=order.contact_email)
    db.commit()
    return CheckoutResult(order_id=order.id, order_code=order.order_code,
                          status="PAGO_PENDIENTE", payment_status=pay_status,
                          total=float(order.total),
                          message=f"Pago {pay_status}. Quedo en revision.")
