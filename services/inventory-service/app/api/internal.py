"""Endpoints internos consumidos por Commerce durante la SAGA del checkout:

- POST /reserve : reserva multiple variantes con lock distribuido por variante.
                  Cualquier item sin stock revierte TODA la operacion (transaccion).
- POST /confirm/{order_id} : convierte reservas en venta definitiva (stock -= qty,
                              reserved_stock -= qty). Llamado tras PaymentApproved.
- POST /release/{order_id} : libera reservas (compensacion). Llamado tras
                              PaymentRejected o cancelacion.
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
    """Reserva atomica de varias variantes para un order_id.

    Usa lock distribuido Redis por variante (evita doble reserva concurrente).
    Si Redis no esta disponible, cae a SELECT FOR UPDATE en MySQL.

    Si CUALQUIER item falla, la transaccion completa se revierte y se devuelve
    409 Conflict listando que items fallaron. Esto evita reservas parciales.
    """
    if not payload.items:
        raise HTTPException(422, "Lista de items vacia.")

    # 1. Adquirir locks distribuidos en orden ASC para evitar deadlocks
    locks_taken: list = []
    user_id = int(claims["sub"]) if claims.get("sub") else None
    variant_ids = sorted({i.variant_id for i in payload.items})

    try:
        for vid in variant_ids:
            try:
                cm = redis_lock.acquire(f"lock:variant:{vid}", ttl_seconds=5)
                cm.__enter__()
                locks_taken.append(cm)
            except TimeoutError:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail=f"Variante {vid} esta siendo reservada por otra compra. Reintente.",
                )

        # 2. Bloquear filas en MySQL y validar stock disponible
        items_by_variant: dict[int, int] = {}
        for it in payload.items:
            items_by_variant[it.variant_id] = items_by_variant.get(it.variant_id, 0) + it.quantity

        variants_locked: dict[int, ProductVariant] = {}
        unavailable: list[dict] = []
        for vid, qty_needed in items_by_variant.items():
            v = (
                db.query(ProductVariant)
                .filter(ProductVariant.id == vid)
                .with_for_update()
                .first()
            )
            if not v:
                unavailable.append({"variant_id": vid, "reason": "no_existe"})
                continue
            if not v.active:
                unavailable.append({"variant_id": vid, "reason": "inactiva"})
                continue
            if v.available < qty_needed:
                unavailable.append({
                    "variant_id": vid, "reason": "sin_stock",
                    "requested": qty_needed, "available": v.available,
                })
                continue
            variants_locked[vid] = v

        if unavailable:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, detail={"unavailable": unavailable})

        # 3. Crear reservas y registrar movimientos
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            seconds=payload.ttl_seconds
        )
        reservation_ids: list[int] = []
        result_items: list[dict] = []
        subtotal = 0.0

        for it in payload.items:
            v = variants_locked[it.variant_id]
            v.reserved_stock += it.quantity
            res = StockReservation(
                variant_id=v.id,
                order_id=payload.order_id,
                quantity=it.quantity,
                status="PENDING",
                expires_at=expires_at,
            )
            db.add(res)
            db.add(StockMovement(
                variant_id=v.id,
                movement_type="reserve",
                quantity=it.quantity,
                reason=f"Reserva para orden {payload.order_id}",
                user_id=user_id,
                order_id=payload.order_id,
                correlation_id=correlation_id,
            ))
            db.flush()
            reservation_ids.append(res.id)
            line_total = float(v.price) * it.quantity
            subtotal += line_total
            result_items.append({
                "variant_id": v.id,
                "sku": v.sku,
                "quantity": it.quantity,
                "unit_price": float(v.price),
                "line_total": line_total,
            })

        db.commit()
        return ReserveResponse(
            order_id=payload.order_id,
            reservation_ids=reservation_ids,
            expires_at=expires_at,
            items=result_items,
            subtotal=subtotal,
        )
    finally:
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
    """Convierte reservas PENDING en venta definitiva: stock -= qty."""
    user_id = int(claims["sub"]) if claims.get("sub") else None
    pendings = (
        db.query(StockReservation)
        .filter(StockReservation.order_id == order_id, StockReservation.status == "PENDING")
        .all()
    )
    if not pendings:
        raise HTTPException(404, f"No hay reservas PENDING para order_id={order_id}.")

    affected = 0
    for r in pendings:
        v = (
            db.query(ProductVariant)
            .filter(ProductVariant.id == r.variant_id)
            .with_for_update()
            .first()
        )
        if not v:
            continue
        # stock fisico -= cantidad; reserved_stock -= cantidad
        v.stock = max(0, v.stock - r.quantity)
        v.reserved_stock = max(0, v.reserved_stock - r.quantity)
        r.status = "CONFIRMED"
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
    """Libera reservas PENDING (compensacion de la SAGA)."""
    user_id = int(claims["sub"]) if claims.get("sub") else None
    pendings = (
        db.query(StockReservation)
        .filter(StockReservation.order_id == payload.order_id, StockReservation.status == "PENDING")
        .all()
    )
    affected = 0
    for r in pendings:
        v = (
            db.query(ProductVariant)
            .filter(ProductVariant.id == r.variant_id)
            .with_for_update()
            .first()
        )
        if v:
            v.reserved_stock = max(0, v.reserved_stock - r.quantity)
        r.status = "RELEASED"
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
