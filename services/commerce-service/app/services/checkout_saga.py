"""Orquestador de la SAGA orquestada sincrona del checkout.

Materializa el diagrama 11.0 del informe Fase 1.

Politica del MVP (revision mayo 2026):

   La Order SOLO se persiste si el checkout termina en PAID.

   Casos antes implementados como estados artificiales del pedido
   (PAGO_RECHAZADO, PAGO_PENDIENTE, SIN_STOCK) ya no producen una fila en
   `orders`. En su lugar:
     - El cliente recibe un error HTTP claro (409 / 402 / 503).
     - Los intentos fallidos quedan registrados como FailedCheckoutAttempt
       (bitacora) para trazabilidad, sin contaminar el listado de pedidos
       del admin ni inflar metricas financieras.
     - La reserva de Inventory se libera siempre que aplica.

Eso mantiene la SAGA orquestada y la compensacion HTTP (cumple bloque 6 del
informe), pero entrega una UX mucho mas alineada a un ecommerce real.
"""
import logging
from typing import TypedDict

from sqlalchemy.orm import Session

from app.models import (
    Cart,
    FailedCheckoutAttempt,
    Notification,
    Order,
    OrderAuditLog,
    OrderItem,
    OrderStatusHistory,
)
from app.services.http_clients import (
    ServiceUnavailable,
    inventory_confirm,
    inventory_get_variants_by_ids,
    inventory_release,
    inventory_reserve,
    payment_charge,
)
from app.services.mailer import send_email

logger = logging.getLogger(__name__)


class CheckoutOK(TypedDict):
    order_id: int
    order_code: str
    status: str
    payment_status: str
    total: float
    message: str


class CheckoutError(Exception):
    """El checkout fallo de forma controlada. status_code es el codigo HTTP a
    devolver al cliente; payload es el cuerpo JSON con la razon."""

    def __init__(self, status_code: int, code: str, message: str,
                 extra: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = {"code": code, "message": message, **(extra or {})}


def _record_failure(db: Session, *, user_id: int, attempt_code: str,
                    reason_code: str, message: str, subtotal: float,
                    correlation_id: str | None, payload: str | None = None) -> None:
    """Registra el intento fallido para auditoria sin crear una Order."""
    db.add(FailedCheckoutAttempt(
        user_id=user_id, attempt_code=attempt_code,
        reason_code=reason_code, message=message[:500],
        subtotal=subtotal, correlation_id=correlation_id,
        payload=(payload or "")[:2000],
    ))
    db.add(OrderAuditLog(
        order_id=None, action=f"checkout_failed_{reason_code}",
        performed_by=user_id, details=message[:2000],
        correlation_id=correlation_id,
    ))


def _notify_user(db: Session, user_id: int, order_id: int | None, title: str,
                 message: str, email: str | None = None) -> None:
    db.add(Notification(user_id=user_id, order_id=order_id, title=title, message=message))
    if email:
        send_email(email, title, message)


def execute_checkout(
    db: Session,
    *,
    cart: Cart,
    user_id: int,
    token: str,
    correlation_id: str,
    delivery_name: str,
    delivery_address: str,
    delivery_city: str,
    billing_document: str,
    contact_phone: str,
    contact_email: str,
    card_token: str | None,
    attempt_code: str,
    subtotal: float,
    total: float,
) -> CheckoutOK:
    """Ejecuta la SAGA y devuelve el resultado.

    Lanza `CheckoutError` con codigo HTTP claro si el flujo no llega a PAID.
    NO crea Order salvo que el pago sea APPROVED.
    """
    items_payload = [{"variant_id": i.variant_id, "quantity": i.quantity} for i in cart.items]
    if not items_payload:
        raise CheckoutError(400, "cart_empty", "Tu carrito esta vacio.")

    # ─── 1. RESERVAR INVENTARIO ─────────────────────────────────────────────
    try:
        resp = inventory_reserve(attempt_code, items_payload, token, correlation_id)
    except ServiceUnavailable as exc:
        _record_failure(db, user_id=user_id, attempt_code=attempt_code,
                        reason_code="inventory_unavailable",
                        message=f"Inventory no respondio: {exc}",
                        subtotal=subtotal, correlation_id=correlation_id)
        db.commit()
        raise CheckoutError(
            503, "inventory_unavailable",
            "El servicio de inventario no está disponible. Intenta de nuevo en unos minutos."
        ) from exc

    if resp["status_code"] == 409:
        body = resp["body"] if isinstance(resp["body"], dict) else {}
        unavailable = (body.get("detail") or {}).get("unavailable") if isinstance(body.get("detail"), dict) else None
        msg = "Uno o más productos del carrito ya no tienen stock suficiente."
        _record_failure(db, user_id=user_id, attempt_code=attempt_code,
                        reason_code="out_of_stock", message=msg,
                        subtotal=subtotal, correlation_id=correlation_id,
                        payload=str(body)[:1000])
        db.commit()
        raise CheckoutError(409, "out_of_stock", msg, {"unavailable": unavailable})

    if resp["status_code"] not in (200, 201):
        msg = f"Inventory respondio {resp['status_code']} al reservar."
        _record_failure(db, user_id=user_id, attempt_code=attempt_code,
                        reason_code="inventory_error", message=msg,
                        subtotal=subtotal, correlation_id=correlation_id,
                        payload=str(resp.get("body", ""))[:1000])
        db.commit()
        raise CheckoutError(502, "inventory_error",
                            "No fue posible reservar inventario. Intenta de nuevo.")

    # ─── 2. COBRAR ──────────────────────────────────────────────────────────
    try:
        pay = payment_charge(attempt_code, total, "COP", token,
                             card_token=card_token, correlation_id=correlation_id)
    except ServiceUnavailable as exc:
        # Compensacion: liberar el stock reservado.
        inventory_release(attempt_code, "payment_service_unavailable", token, correlation_id)
        _record_failure(db, user_id=user_id, attempt_code=attempt_code,
                        reason_code="payment_unavailable",
                        message=f"Pasarela no disponible: {exc}",
                        subtotal=subtotal, correlation_id=correlation_id)
        db.commit()
        raise CheckoutError(
            503, "payment_unavailable",
            "La pasarela de pagos no está disponible en este momento. "
            "Tu carrito quedó intacto; intenta de nuevo en unos minutos."
        ) from exc

    body = pay["body"] if isinstance(pay["body"], dict) else {}
    pay_status = body.get("status", "FAILED")
    payment_id = body.get("payment_id")
    payment_reference = body.get("transaction_reference")
    payment_message = (body.get("message") or "")[:250]

    # Caso "Circuit Breaker abierto" → Payment devuelve 503
    if pay["status_code"] == 503:
        inventory_release(attempt_code, "payment_circuit_open", token, correlation_id)
        _record_failure(db, user_id=user_id, attempt_code=attempt_code,
                        reason_code="payment_circuit_open",
                        message="Circuit Breaker de la pasarela esta OPEN.",
                        subtotal=subtotal, correlation_id=correlation_id)
        db.commit()
        raise CheckoutError(
            503, "payment_unavailable",
            "La pasarela está temporalmente fuera de servicio (modo protegido). "
            "Intenta en unos minutos."
        )

    if pay_status == "REJECTED":
        # Compensacion + bitacora; NO se crea Order.
        inventory_release(attempt_code, "payment_rejected", token, correlation_id)
        _record_failure(db, user_id=user_id, attempt_code=attempt_code,
                        reason_code="payment_rejected",
                        message=f"Pago rechazado: {payment_message}",
                        subtotal=subtotal, correlation_id=correlation_id,
                        payload=str(body)[:1000])
        # Notificacion in-app + correo (sin order_id porque no existe)
        _notify_user(db, user_id, None, "Pago rechazado",
                     f"Tu pago no fue aprobado por la pasarela. Razón: {payment_message or 'sin detalle'}. "
                     "Puedes intentar de nuevo con otro método.",
                     email=contact_email)
        db.commit()
        raise CheckoutError(
            402, "payment_rejected",
            payment_message or "El pago fue rechazado por la pasarela. Intenta con otro método.",
        )

    if pay_status not in ("APPROVED",):
        # PENDING / FAILED del mock → tratamos como no aprobado: compensamos y avisamos.
        inventory_release(attempt_code, f"payment_{pay_status.lower()}", token, correlation_id)
        _record_failure(db, user_id=user_id, attempt_code=attempt_code,
                        reason_code=f"payment_{pay_status.lower()}",
                        message=f"Pago en estado {pay_status}",
                        subtotal=subtotal, correlation_id=correlation_id,
                        payload=str(body)[:1000])
        db.commit()
        raise CheckoutError(
            502, "payment_not_approved",
            f"La pasarela devolvió estado {pay_status}. Intenta de nuevo.",
        )

    # ─── 3. PAGO APROBADO: AHORA SI CREAMOS LA ORDER ────────────────────────
    # Snapshot del costo unitario (para COGS y margenes)
    variant_ids = list({i.variant_id for i in cart.items})
    cost_map = inventory_get_variants_by_ids(variant_ids)

    order = Order(
        order_code=attempt_code, user_id=user_id, status="PAID",
        payment_status="APPROVED", payment_id=payment_id,
        payment_reference=payment_reference, payment_message=payment_message,
        subtotal=subtotal, additional_costs=0, discount=0, total=total, currency="COP",
        delivery_name=delivery_name, delivery_address=delivery_address,
        delivery_city=delivery_city, billing_document=billing_document,
        contact_phone=contact_phone, contact_email=contact_email,
        correlation_id=correlation_id,
    )
    db.add(order)
    db.flush()

    for it in cart.items:
        info = cost_map.get(it.variant_id, {})
        unit_cost = float(info.get("cost") or 0)
        db.add(OrderItem(
            order_id=order.id, variant_id=it.variant_id, product_id=it.product_id,
            product_name=it.product_name, variant_description=it.variant_description,
            image_url=it.image_url, quantity=it.quantity,
            unit_price=float(it.unit_price),
            unit_cost=unit_cost,
            total=float(it.unit_price) * it.quantity,
        ))

    db.add(OrderStatusHistory(order_id=order.id, from_status=None, to_status="PAID",
                              changed_by=user_id, notes="Checkout exitoso (SAGA OK)"))
    db.add(OrderAuditLog(order_id=order.id, action="payment_approved",
                         performed_by=user_id,
                         details=f"ref={payment_reference}", correlation_id=correlation_id))

    # Confirmar inventario (descuenta el stock fisico)
    ok = inventory_confirm(attempt_code, token, correlation_id)
    if not ok:
        db.add(OrderAuditLog(order_id=order.id, action="confirm_after_paid_failed",
                             performed_by=user_id,
                             details="Inventory confirm fallo tras PAID; reserva vencera y stock no bajara.",
                             correlation_id=correlation_id))

    # Notificacion + correo
    _notify_user(db, user_id, order.id, "Compra exitosa",
                 f"Tu pedido {order.order_code} fue pagado con éxito.\n"
                 f"Total: ${float(order.total):,.0f} {order.currency}\n"
                 f"Te avisaremos cuando lo preparemos y despachemos.",
                 email=contact_email)
    cart.status = "checked_out"
    db.commit()
    return CheckoutOK(
        order_id=order.id, order_code=order.order_code,
        status="PAID", payment_status="APPROVED",
        total=float(order.total),
        message="Pago aprobado. Compra confirmada.",
    )
