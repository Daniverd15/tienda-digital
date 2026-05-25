"""Orquestador de la SAGA orquestada sincrona del checkout.

================================================================================
PROPOSITO
================================================================================
Este modulo es el CORAZON del sistema. Coordina los 3 microservicios criticos
(Inventory, Payment, Commerce) durante el checkout para garantizar que:

  1. NO se descuenta stock sin pago confirmado.
  2. NO se cobra al cliente sin tener stock disponible.
  3. Si CUALQUIER paso falla, se compensa (libera reserva) y NO queda Order.

Materializa el patron SAGA orquestada sincrona descrito en el informe Fase 1,
seccion 11.0. La "orquestacion" significa que Commerce decide el orden de las
llamadas; la "sincrona" significa que cada paso espera la respuesta del
siguiente antes de continuar.

================================================================================
POLITICA DEL MVP (revision mayo 2026)
================================================================================
La Order SOLO se persiste si el checkout termina en PAID.

Casos antes implementados como estados artificiales del pedido (PAGO_RECHAZADO,
PAGO_PENDIENTE, SIN_STOCK) ya NO producen una fila en la tabla `orders`. En su
lugar:
  - El cliente recibe un error HTTP claro (409 / 402 / 503).
  - Los intentos fallidos quedan registrados como FailedCheckoutAttempt
    (tabla de bitacora) para trazabilidad y soporte, SIN contaminar el
    listado de pedidos del admin ni inflar metricas financieras.
  - La reserva de Inventory se libera siempre que aplica (compensacion).

Eso mantiene la SAGA orquestada y la compensacion HTTP (cumple bloque 6 del
informe), pero entrega una UX mucho mas alineada a un ecommerce real.

================================================================================
FLUJO HAPPY PATH
================================================================================
  Cliente -> Frontend -> Gateway -> Commerce (este modulo)
                                        |
                                        | 1. POST /reserve (Inventory)
                                        |    └─ Lock distribuido + SELECT FOR UPDATE
                                        |
                                        | 2. POST /payments (Payment)
                                        |    └─ Circuit Breaker check + POST /charge
                                        |
                                        | 3. POST /confirm/{id} (Inventory)
                                        |    └─ stock -= qty
                                        |
                                        | 4. Persistir Order(PAID) + OrderItems
                                        | 5. Notificacion + correo SMTP
                                        | 6. Marcar carrito como checked_out
                                        v
                              Devuelve 201 Created al cliente

================================================================================
FLUJOS DE COMPENSACION
================================================================================
- Sin stock (paso 1 falla)      → 409, no se crea Order, no se cobra
- Payment unavailable (paso 2)  → 503, se libera reserva (compensacion)
- Pago REJECTED (paso 2)        → 402, se libera reserva, NO se crea Order
- Circuit Breaker OPEN (paso 2) → 503, se libera reserva
- Inventory confirm falla (3)   → caso raro: Order queda PAID + audit; el
                                  scheduler de Inventory libera la reserva
                                  vencida y un admin debera revisar
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


# --------------------------------------------------------------------------
# TIPOS DE RETORNO DE LA SAGA
# --------------------------------------------------------------------------

class CheckoutOK(TypedDict):
    """Resultado exitoso del checkout (cuando el flujo llega a PAID).

    Se serializa directamente como JSON a la respuesta HTTP 201.
    """
    order_id: int
    order_code: str
    status: str           # siempre "PAID" en este punto
    payment_status: str   # siempre "APPROVED"
    total: float
    message: str


class CheckoutError(Exception):
    """Excepcion controlada cuando la SAGA no llega a PAID.

    El endpoint /checkout la captura y la traduce a JSONResponse con el
    status_code y payload correspondiente. NO es un crash: es una salida
    "esperada" del flujo (cliente sin stock, pago rechazado, etc.).

    Atributos:
        status_code: codigo HTTP a devolver al cliente (409, 402, 503, 502).
        payload: cuerpo JSON con {code, message, ...extra} para el frontend.
    """

    def __init__(self, status_code: int, code: str, message: str,
                 extra: dict | None = None):
        """Construye el payload que el endpoint devuelve al frontend."""
        super().__init__(message)
        self.status_code = status_code
        # El payload incluye un `code` machine-readable para que el frontend
        # pueda mapearlo a iconos y mensajes especificos (out_of_stock,
        # payment_rejected, etc.).
        self.payload = {"code": code, "message": message, **(extra or {})}


# --------------------------------------------------------------------------
# HELPERS INTERNOS
# --------------------------------------------------------------------------

def _record_failure(db: Session, *, user_id: int, attempt_code: str,
                    reason_code: str, message: str, subtotal: float,
                    correlation_id: str | None, payload: str | None = None) -> None:
    """Registra un intento de checkout fallido en la tabla de auditoria.

    NO crea Order. Crea:
      - Una fila en FailedCheckoutAttempt (para soporte: "por que el cliente
        no pudo comprar").
      - Una entrada en OrderAuditLog con order_id=None (bitacora unificada
        que cruza con eventos exitosos via correlation_id).

    Los campos message y payload se truncan para evitar inflar la BD si la
    pasarela devuelve cuerpos enormes.
    """
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
    """Crea una notificacion in-app + envia correo al cliente.

    Se invoca cuando hay un evento relevante (compra exitosa, pago rechazado,
    pasarela caida) para que el cliente reciba feedback inmediato. El
    order_id puede ser None si todavia no existe la Order (caso de fallo
    antes del paso 3). El correo se envia best-effort (si SMTP cae, la
    notificacion in-app igual se crea).
    """
    db.add(Notification(user_id=user_id, order_id=order_id, title=title, message=message))
    if email:
        send_email(email, title, message)


# --------------------------------------------------------------------------
# ORQUESTADOR PRINCIPAL DE LA SAGA
# --------------------------------------------------------------------------

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
    """Ejecuta la SAGA del checkout coordinando Inventory + Payment + Commerce.

    Es el unico punto de entrada al flujo de checkout desde el endpoint
    POST /checkout. Recibe TODOS los datos ya validados por Pydantic y solo
    se encarga de la orquestacion.

    Devuelve CheckoutOK si llega a PAID.
    Lanza CheckoutError(status_code, code, message) en cualquier otro caso.

    El caller (api/checkout.py) traduce la excepcion a JSONResponse con el
    codigo HTTP apropiado.
    """
    # Convertimos los items del carrito al formato que espera /reserve.
    # Cada item lleva variant_id + quantity (no necesitamos enviar precio
    # porque Inventory es la fuente de verdad).
    items_payload = [{"variant_id": i.variant_id, "quantity": i.quantity} for i in cart.items]
    if not items_payload:
        raise CheckoutError(400, "cart_empty", "Tu carrito esta vacio.")

    # ═══════════════════════════════════════════════════════════════════
    # PASO 1: RESERVAR INVENTARIO
    # ═══════════════════════════════════════════════════════════════════
    # Llamamos a Inventory.POST /reserve. Si exitoso, Inventory:
    #   - Adquiere lock distribuido Redis por variante (SET NX EX)
    #   - Hace SELECT FOR UPDATE en MySQL sobre las filas de variantes
    #   - Verifica que (stock - reserved_stock) >= quantity para CADA item
    #   - Crea StockReservation con TTL de 15 minutos
    #   - Devuelve los reservation_ids al caller
    # Si Inventory no responde (timeout, connection refused) → ServiceUnavailable.
    try:
        resp = inventory_reserve(attempt_code, items_payload, token, correlation_id)
    except ServiceUnavailable as exc:
        # Inventory esta caido. No tenemos que liberar nada (no se reservo)
        # pero registramos el intento para soporte.
        _record_failure(db, user_id=user_id, attempt_code=attempt_code,
                        reason_code="inventory_unavailable",
                        message=f"Inventory no respondio: {exc}",
                        subtotal=subtotal, correlation_id=correlation_id)
        db.commit()
        raise CheckoutError(
            503, "inventory_unavailable",
            "El servicio de inventario no está disponible. Intenta de nuevo en unos minutos."
        ) from exc

    # Inventory respondio 409 → algun item NO tiene stock suficiente.
    # En el body viene la lista de items insuficientes para que el frontend
    # los muestre al cliente.
    if resp["status_code"] == 409:
        body = resp["body"] if isinstance(resp["body"], dict) else {}
        unavailable = (body.get("detail") or {}).get("unavailable") if isinstance(body.get("detail"), dict) else None
        msg = "Uno o más productos del carrito ya no tienen stock suficiente."
        _record_failure(db, user_id=user_id, attempt_code=attempt_code,
                        reason_code="out_of_stock", message=msg,
                        subtotal=subtotal, correlation_id=correlation_id,
                        payload=str(body)[:1000])
        db.commit()
        # Devolvemos el detalle de items sin stock para que el frontend lo
        # muestre en la pantalla de error con cantidades.
        raise CheckoutError(409, "out_of_stock", msg, {"unavailable": unavailable})

    # Cualquier otro codigo != 201 es un error inesperado de Inventory.
    if resp["status_code"] not in (200, 201):
        msg = f"Inventory respondio {resp['status_code']} al reservar."
        _record_failure(db, user_id=user_id, attempt_code=attempt_code,
                        reason_code="inventory_error", message=msg,
                        subtotal=subtotal, correlation_id=correlation_id,
                        payload=str(resp.get("body", ""))[:1000])
        db.commit()
        raise CheckoutError(502, "inventory_error",
                            "No fue posible reservar inventario. Intenta de nuevo.")

    # ═══════════════════════════════════════════════════════════════════
    # PASO 2: COBRAR A TRAVES DE LA PASARELA
    # ═══════════════════════════════════════════════════════════════════
    # Llamamos a Payment.POST /payments. Internamente Payment:
    #   - Verifica el Circuit Breaker (si OPEN, devuelve 503 SIN tocar la pasarela)
    #   - Llama a POST /charge del payment-mock
    #   - Aplica reintentos exponenciales si hay errores transitorios (5xx)
    #   - Devuelve el resultado APPROVED / REJECTED / PENDING / FAILED
    try:
        pay = payment_charge(attempt_code, total, "COP", token,
                             card_token=card_token, correlation_id=correlation_id)
    except ServiceUnavailable as exc:
        # Payment Service esta caido completamente. COMPENSAMOS liberando la
        # reserva para que el stock no quede bloqueado los 15 minutos del TTL.
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

    # Parseo defensivo del body (puede no ser dict si algo raro paso).
    body = pay["body"] if isinstance(pay["body"], dict) else {}
    pay_status = body.get("status", "FAILED")
    payment_id = body.get("payment_id")
    payment_reference = body.get("transaction_reference")
    # Truncamos el message porque la pasarela podria devolver textos largos
    # que no caben en VARCHAR(250) de Order.payment_message.
    payment_message = (body.get("message") or "")[:250]

    # Caso: Circuit Breaker abierto → Payment devuelve 503 sin tocar la pasarela.
    # Esto sucede cuando hubo 5 fallos consecutivos previos (proteccion al sistema).
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

    # Caso: pago REJECTED. La pasarela rechazo el pago (fondos insuficientes,
    # tarjeta vencida, etc.). COMPENSAMOS liberando stock + notificamos cliente.
    if pay_status == "REJECTED":
        inventory_release(attempt_code, "payment_rejected", token, correlation_id)
        _record_failure(db, user_id=user_id, attempt_code=attempt_code,
                        reason_code="payment_rejected",
                        message=f"Pago rechazado: {payment_message}",
                        subtotal=subtotal, correlation_id=correlation_id,
                        payload=str(body)[:1000])
        # Notificacion in-app + correo. Sin order_id porque NO se crea Order.
        _notify_user(db, user_id, None, "Pago rechazado",
                     f"Tu pago no fue aprobado por la pasarela. Razón: {payment_message or 'sin detalle'}. "
                     "Puedes intentar de nuevo con otro método.",
                     email=contact_email)
        db.commit()
        # 402 Payment Required: codigo HTTP semantico para "pago rechazado".
        raise CheckoutError(
            402, "payment_rejected",
            payment_message or "El pago fue rechazado por la pasarela. Intenta con otro método.",
        )

    # Caso: pago PENDING o FAILED. La pasarela no aprobo pero tampoco rechazo
    # explicitamente. Para el MVP los tratamos como "no aprobado" → compensamos.
    # En un sistema real, PENDING podria llevarse a una cola de reconciliacion.
    if pay_status not in ("APPROVED",):
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

    # ═══════════════════════════════════════════════════════════════════
    # PASO 3: PAGO APROBADO → CREAR LA ORDER
    # ═══════════════════════════════════════════════════════════════════
    # A partir de aqui sabemos que:
    #   - El stock esta reservado (no podemos perderlo)
    #   - El pago fue APPROVED (la pasarela ya cobro)
    # Por lo tanto creamos la Order y la persistimos definitivamente.

    # 3.1 Snapshot del costo unitario para calculo posterior de COGS.
    # Llamamos a Inventory por batch para obtener cost de cada variante en
    # UNA sola request en vez de N. El costo se "congela" en el OrderItem
    # para que el dashboard financiero use el costo del momento del checkout
    # (aunque mañana cambie el costo del producto, los pedidos historicos
    # mantienen el COGS correcto).
    variant_ids = list({i.variant_id for i in cart.items})
    cost_map = inventory_get_variants_by_ids(variant_ids)

    # 3.2 Crear la Order con TODOS los datos: pago, dirigida, totales.
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
    # flush() ejecuta el INSERT sin commitear: nos asigna el order.id para
    # poder referenciarlo en OrderItems sin esperar al commit final.
    db.flush()

    # 3.3 Crear los OrderItems uno por uno. Snapshoteamos:
    #   - product_name, variant_description, image_url: por si el producto
    #     cambia despues, el pedido conserva el snapshot.
    #   - unit_price: precio al momento de la compra (no precio actual).
    #   - unit_cost: costo al momento de la compra (para COGS historico).
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

    # 3.4 Bitacora: historia de estados + audit log.
    # OrderStatusHistory: timeline visible al cliente con cada transicion.
    db.add(OrderStatusHistory(order_id=order.id, from_status=None, to_status="PAID",
                              changed_by=user_id, notes="Checkout exitoso (SAGA OK)"))
    # OrderAuditLog: bitacora administrativa con correlation_id para cruzar
    # con los logs de los otros microservicios.
    db.add(OrderAuditLog(order_id=order.id, action="payment_approved",
                         performed_by=user_id,
                         details=f"ref={payment_reference}", correlation_id=correlation_id))

    # 3.5 CONFIRMAR la reserva en Inventory. Esto descuenta el stock real
    # (stock -= qty, reserved_stock -= qty). Si falla, la Order ya esta
    # creada en PAID, pero el stock no bajo. Es un caso raro (Inventory
    # respondio /reserve pero no /confirm). El scheduler de Inventory
    # liberara la reserva al expirar y un admin debera revisar.
    ok = inventory_confirm(attempt_code, token, correlation_id)
    if not ok:
        db.add(OrderAuditLog(order_id=order.id, action="confirm_after_paid_failed",
                             performed_by=user_id,
                             details="Inventory confirm fallo tras PAID; reserva vencera y stock no bajara.",
                             correlation_id=correlation_id))

    # 3.6 Notificacion al cliente: in-app (siempre) + correo (best effort).
    _notify_user(db, user_id, order.id, "Compra exitosa",
                 f"Tu pedido {order.order_code} fue pagado con éxito.\n"
                 f"Total: ${float(order.total):,.0f} {order.currency}\n"
                 f"Te avisaremos cuando lo preparemos y despachemos.",
                 email=contact_email)

    # 3.7 Marcar el carrito como checked_out para que el cliente arranque
    # con uno vacio en la proxima visita. La proxima vez que GET /cart
    # devuelva, creara un Cart nuevo en estado "open".
    cart.status = "checked_out"

    # Commit final: TODO lo anterior se persiste en una sola transaccion
    # MySQL. Si algo en este commit falla, el rollback automatico deshace
    # la Order entera (pero el stock ya esta descontado en Inventory por la
    # llamada a /confirm que paso antes — eso queda inconsistente; en
    # produccion real esto requeriria un Outbox Pattern, pero es aceptable
    # para el MVP academico).
    db.commit()

    return CheckoutOK(
        order_id=order.id, order_code=order.order_code,
        status="PAID", payment_status="APPROVED",
        total=float(order.total),
        message="Pago aprobado. Compra confirmada.",
    )
