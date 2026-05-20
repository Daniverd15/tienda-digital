"""Endpoints internos consumidos por Commerce durante la SAGA del checkout.

================================================================================
PROPOSITO
================================================================================
Estos tres endpoints implementan los pasos de la SAGA orquestada vista desde
Inventory:

  - POST /reserve              → paso 1 de la SAGA. Reserva stock atomicamente
                                  por TTL (default 15 min). Si falla → 409.
  - POST /confirm/{order_id}   → paso 3 de la SAGA (despues de cobrar).
                                  Convierte la reserva en venta definitiva:
                                  stock -= qty, reserved_stock -= qty.
  - POST /release              → COMPENSACION. Libera la reserva sin descontar
                                  stock cuando el pago falla.

================================================================================
GARANTIA DE CONSISTENCIA EN CONCURRENCIA
================================================================================
Dos clientes que intenten reservar la ULTIMA unidad de una variante deben
recibir uno OK y otro 409, nunca ambos OK (sobreventa).

Para lograrlo usamos DOS niveles de bloqueo:

  1. Lock distribuido Redis (SET NX EX por variante): rapido, evita que dos
     procesos entren a la zona critica al mismo tiempo.

  2. SELECT FOR UPDATE en MySQL: lock pesimista por fila. Es la garantia
     definitiva: si Redis cae, MySQL sigue protegiendo. La transaccion
     completa se hace commit junta para que reserved_stock se actualice
     atomicamente con la creacion de la StockReservation.

Los locks se adquieren en ORDEN ASCENDENTE de variant_id para evitar
deadlocks: si dos checkouts comparten dos variantes, ambos las pediran
en el mismo orden y uno esperara al otro en vez de quedarse en deadlock.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core import redis_lock
from app.core.database import get_db
from app.core.deps import get_correlation_id, require_internal_or_user
from app.models import ProductVariant, StockMovement, StockReservation
from app.schemas import (
    ApiMessage,
    ReserveRequest,
    ReserveResponse,
    ReleaseRequest,
)


router = APIRouter(tags=["Inventario interno"])


@router.post("/reserve", response_model=ReserveResponse, status_code=status.HTTP_201_CREATED)
def reserve(
    payload: ReserveRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_internal_or_user),
    correlation_id: str = Depends(get_correlation_id),
):
    """Reserva atomica de varias variantes para un order_id (PASO 1 SAGA).

    Body:
        order_id: codigo del pedido (string, generado por Commerce)
        items: list[{variant_id, quantity}]
        ttl_seconds: cuanto vive la reserva antes de expirar (default 900s = 15min)

    Respuestas:
        201 → reserva exitosa con lista de reservation_ids
        409 → algun item sin stock o lock ocupado (body lleva `unavailable`)
        422 → lista de items vacia

    Garantia: si CUALQUIER item del payload no se puede reservar, NINGUN
    item se reserva (atomicidad). El cliente recibe el listado completo
    de items problematicos para que pueda ajustar el carrito.
    """
    if not payload.items:
        raise HTTPException(422, "Lista de items vacia.")

    # ─── 1. ADQUIRIR LOCKS DISTRIBUIDOS POR VARIANTE ─────────────────────
    # Tomamos los locks en orden ASCENDENTE de variant_id para evitar
    # deadlocks (si dos checkouts comparten dos variantes, ambos las pediran
    # en el mismo orden y uno esperara al otro).
    locks_taken: list = []
    user_id = int(claims["sub"]) if claims.get("sub") else None
    # set() para eliminar duplicados (si el cliente puso la misma variante
    # dos veces en el carrito por algun bug, no necesitamos lockearla dos veces).
    variant_ids = sorted({i.variant_id for i in payload.items})

    try:
        for vid in variant_ids:
            try:
                # Adquirir lock con TTL corto (5s). Si Redis cae, el lock es
                # no-op pero el SELECT FOR UPDATE de MySQL nos protege.
                cm = redis_lock.acquire(f"lock:variant:{vid}", ttl_seconds=5)
                cm.__enter__()
                locks_taken.append(cm)
            except TimeoutError:
                # Otro proceso ya tiene el lock de esta variante. Es comun
                # en alta concurrencia: el cliente puede reintentar.
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail=f"Variante {vid} esta siendo reservada por otra compra. Reintente.",
                )

        # ─── 2. AGRUPAR CANTIDADES POR VARIANTE ──────────────────────────
        # Si el cliente puso la misma variante 2 veces en el carrito
        # (cantidad=3 y cantidad=2), sumamos a 5 antes de validar stock.
        items_by_variant: dict[int, int] = {}
        for it in payload.items:
            items_by_variant[it.variant_id] = items_by_variant.get(it.variant_id, 0) + it.quantity

        # ─── 3. SELECT FOR UPDATE + VALIDAR STOCK DE CADA VARIANTE ──────
        variants_locked: dict[int, ProductVariant] = {}
        unavailable: list[dict] = []
        for vid, qty_needed in items_by_variant.items():
            # SELECT FOR UPDATE: lock pesimista de la fila en MySQL.
            # Garantia: si otro proceso quiere actualizar reserved_stock
            # de esta variante, esperara a que nuestro commit/rollback
            # termine.
            v = (
                db.query(ProductVariant)
                .filter(ProductVariant.id == vid)
                .with_for_update()
                .first()
            )
            # Verificamos casos de error:
            if not v:
                unavailable.append({"variant_id": vid, "reason": "no_existe"})
                continue
            if not v.active:
                unavailable.append({"variant_id": vid, "reason": "inactiva"})
                continue
            # available = stock - reserved_stock (property en la entidad).
            if v.available < qty_needed:
                unavailable.append({
                    "variant_id": vid, "reason": "sin_stock",
                    "requested": qty_needed, "available": v.available,
                })
                continue
            # Pasa todas las validaciones: la marcamos como reservable.
            variants_locked[vid] = v

        # Si HUBO algun item problematico → 409 con el listado completo.
        # Atomicidad: rollback de TODO, ninguna reserva se persiste.
        if unavailable:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, detail={"unavailable": unavailable})

        # ─── 4. CREAR RESERVAS + REGISTRAR MOVIMIENTOS ──────────────────
        # Calculamos expires_at en UTC naive (formato que usa MySQL).
        # El scheduler liberara reservas con expires_at <= now() cada 60s.
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            seconds=payload.ttl_seconds
        )
        reservation_ids: list[int] = []
        result_items: list[dict] = []
        subtotal = 0.0

        for it in payload.items:
            v = variants_locked[it.variant_id]
            # Incrementamos reserved_stock. NO tocamos stock fisico (eso se
            # hace solo en /confirm). available = stock - reserved_stock
            # bajara automaticamente.
            v.reserved_stock += it.quantity
            # Creamos la StockReservation con status=PENDING y TTL.
            res = StockReservation(
                variant_id=v.id,
                order_id=payload.order_id,
                quantity=it.quantity,
                status="PENDING",
                expires_at=expires_at,
            )
            db.add(res)
            # Registramos el movimiento para auditoria (motivo + correlation_id).
            db.add(StockMovement(
                variant_id=v.id,
                movement_type="reserve",
                quantity=it.quantity,
                reason=f"Reserva para orden {payload.order_id}",
                user_id=user_id,
                order_id=payload.order_id,
                correlation_id=correlation_id,
            ))
            # flush para obtener el res.id sin commit.
            db.flush()
            reservation_ids.append(res.id)
            # Calculamos subtotal con el precio actual de la variante (snapshot).
            line_total = float(v.price) * it.quantity
            subtotal += line_total
            result_items.append({
                "variant_id": v.id,
                "sku": v.sku,
                "quantity": it.quantity,
                "unit_price": float(v.price),
                "line_total": line_total,
            })

        # Commit unico: TODAS las reservas + movimientos + updates de
        # reserved_stock se persisten atomicamente. Si algo falla, rollback total.
        db.commit()
        return ReserveResponse(
            order_id=payload.order_id,
            reservation_ids=reservation_ids,
            expires_at=expires_at,
            items=result_items,
            subtotal=subtotal,
        )
    finally:
        # ─── 5. LIBERAR LOCKS REDIS (siempre, incluso si hubo excepcion) ─
        # Los locks tienen TTL de 5s asi que se auto-liberarian eventualmente,
        # pero los liberamos explicitamente para no hacer esperar a otros
        # clientes en cola.
        for cm in locks_taken:
            try:
                cm.__exit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass


@router.post("/confirm/{order_id}", response_model=ApiMessage)
def confirm(
    order_id: str,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_internal_or_user),
    correlation_id: str = Depends(get_correlation_id),
):
    """Convierte reservas PENDING en venta definitiva (PASO 3 SAGA).

    Lo llama Commerce DESPUES de que la pasarela aprueba el pago. Por cada
    StockReservation con status=PENDING:
      1. SELECT FOR UPDATE sobre la variante (lock pesimista MySQL).
      2. stock -= quantity (descuento del stock fisico).
      3. reserved_stock -= quantity (libera la reserva).
      4. Marca la reserva con status=CONFIRMED.
      5. Registra StockMovement de tipo "confirm".

    Devuelve 404 si no hay reservas PENDING para el order_id (caso raro:
    Commerce llama confirm de algo que nunca reservo, o despues de que el
    scheduler ya expiro las reservas por timeout).
    """
    user_id = int(claims["sub"]) if claims.get("sub") else None
    # Buscar TODAS las reservas PENDING del order_id.
    # Order_id es STRING (no FK) porque referencia logicamente al pedido en
    # otro microservicio (Commerce). Database per Service.
    pendings = (
        db.query(StockReservation)
        .filter(StockReservation.order_id == order_id, StockReservation.status == "PENDING")
        .all()
    )
    if not pendings:
        raise HTTPException(404, f"No hay reservas PENDING para order_id={order_id}.")

    affected = 0
    for r in pendings:
        # Lock pesimista sobre la variante.
        v = (
            db.query(ProductVariant)
            .filter(ProductVariant.id == r.variant_id)
            .with_for_update()
            .first()
        )
        if not v:
            # Variante borrada despues de la reserva (caso edge). Saltamos.
            continue
        # DESCUENTO del stock fisico + LIBERACION del reserved_stock.
        # max(0, ...) defensivo para evitar negativos por bugs previos.
        v.stock = max(0, v.stock - r.quantity)
        v.reserved_stock = max(0, v.reserved_stock - r.quantity)
        r.status = "CONFIRMED"
        # Bitacora del movimiento (auditoria + reconciliacion).
        db.add(StockMovement(
            variant_id=v.id,
            movement_type="confirm",
            quantity=r.quantity,
            reason=f"Confirmacion venta orden {order_id}",
            user_id=user_id,
            order_id=order_id,
            correlation_id=correlation_id,
        ))
        affected += 1

    db.commit()
    return ApiMessage(message=f"{affected} reservas confirmadas para {order_id}.")


@router.post("/release", response_model=ApiMessage)
def release(
    payload: ReleaseRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_internal_or_user),
    correlation_id: str = Depends(get_correlation_id),
):
    """Libera reservas PENDING (COMPENSACION de la SAGA).

    Lo llama Commerce cuando un paso posterior de la SAGA falla y necesita
    deshacer la reserva del paso 1. Casos tipicos:
      - Pago REJECTED por la pasarela
      - Circuit Breaker abierto / Payment Service caido
      - Cualquier error inesperado durante el cobro

    Por cada StockReservation con status=PENDING:
      1. SELECT FOR UPDATE sobre la variante.
      2. reserved_stock -= quantity (libera reserva). stock NO se toca.
      3. Marca la reserva con status=RELEASED.
      4. Registra StockMovement de tipo "release" con el motivo del payload.

    A diferencia de /confirm, NO devuelve 404 si no hay reservas: en una
    SAGA con compensaciones es comun llamar release "por las dudas" aunque
    no haya nada que liberar. Devolvemos 200 con affected=0.
    """
    user_id = int(claims["sub"]) if claims.get("sub") else None
    pendings = (
        db.query(StockReservation)
        .filter(StockReservation.order_id == payload.order_id, StockReservation.status == "PENDING")
        .all()
    )
    affected = 0
    for r in pendings:
        # Lock pesimista de la variante.
        v = (
            db.query(ProductVariant)
            .filter(ProductVariant.id == r.variant_id)
            .with_for_update()
            .first()
        )
        if v:
            # Solo bajamos reserved_stock; stock fisico NO cambia (nunca subio).
            v.reserved_stock = max(0, v.reserved_stock - r.quantity)
        # Marcamos la reserva como RELEASED aunque la variante no exista
        # (asi no la procesamos otra vez).
        r.status = "RELEASED"
        # El motivo viene del payload para auditoria especifica:
        # "payment_rejected" vs "payment_service_unavailable" vs etc.
        db.add(StockMovement(
            variant_id=r.variant_id,
            movement_type="release",
            quantity=r.quantity,
            reason=f"Liberacion ({payload.reason}) de orden {payload.order_id}",
            user_id=user_id,
            order_id=payload.order_id,
            correlation_id=correlation_id,
        ))
        affected += 1
    db.commit()
    return ApiMessage(message=f"{affected} reservas liberadas para {payload.order_id}.")
