"""Endpoints administrativos del Inventory Service.

CRUD de variantes (con validacion contra Catalog), movimientos manuales y
gestion de alertas de stock minimo.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_correlation_id, require_admin
from app.models import LowStockAlert, ProductVariant, StockMovement
from app.schemas import (
    ApiMessage,
    LowStockAlertPublic,
    StockMovementPublic,
    StockMovementUpsert,
    VariantAdminCreate,
    VariantAdminUpdate,
    VariantInternal,
)
from app.services.catalog_client import get_product, product_exists
from app.services.scheduler import expire_pending_reservations
from app.services.serializers import serialize_movement, serialize_variant_internal


router = APIRouter(prefix="/admin", tags=["Inventario administracion"])


def _serialize_alert(alert: LowStockAlert, product_cache: dict[int, dict | None]) -> dict:
    variant = alert.variant
    product_id = variant.product_id if variant else None
    product = None
    if product_id is not None:
        if product_id not in product_cache:
            product_cache[product_id] = get_product(product_id)
        product = product_cache[product_id]
    return {
        "id": alert.id,
        "variant_id": alert.variant_id,
        "product_id": product_id,
        "product_name": (product or {}).get("name") or (f"Producto #{product_id}" if product_id else "Producto no disponible"),
        "sku": variant.sku if variant else None,
        "stock": variant.stock if variant else alert.stock_at_alert,
        "available": variant.available if variant else None,
        "threshold": alert.threshold,
        "stock_at_alert": alert.stock_at_alert,
        "resolved": alert.resolved,
        "notes": alert.notes,
        "created_at": alert.created_at,
    }


def _sync_low_stock_alert(db: Session, variant: ProductVariant, default_threshold: int = 5) -> None:
    alert = (
        db.query(LowStockAlert)
        .filter(LowStockAlert.variant_id == variant.id, LowStockAlert.resolved.is_(False))
        .first()
    )
    threshold = alert.threshold if alert else default_threshold
    if alert and variant.stock > threshold:
        alert.resolved = True
    elif not alert and variant.stock <= threshold:
        db.add(LowStockAlert(
            variant_id=variant.id,
            threshold=threshold,
            stock_at_alert=variant.stock,
            notes=f"Stock {variant.stock} <= umbral {threshold}",
        ))


# -----------------------------------------------------------------------------
# Variantes
# -----------------------------------------------------------------------------


@router.get("/variants")
def list_variants(
    product_id: int | None = Query(default=None),
    only_active: bool = Query(default=False),
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    qry = db.query(ProductVariant)
    if product_id:
        qry = qry.filter(ProductVariant.product_id == product_id)
    if only_active:
        qry = qry.filter(ProductVariant.active.is_(True))
    return [serialize_variant_internal(v) for v in qry.order_by(ProductVariant.id.asc()).all()]


@router.post("/variants", status_code=status.HTTP_201_CREATED)
def create_variant(
    payload: VariantAdminCreate,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    # Validacion cross-service: existe el producto en Catalog?
    exists = product_exists(payload.product_id)
    if exists is False:
        raise HTTPException(422, f"product_id={payload.product_id} no existe en Catalog.")
    # exists == None -> Catalog caido, modo degradado, permitimos
    if db.query(ProductVariant).filter(ProductVariant.sku == payload.sku).first():
        raise HTTPException(409, f"Ya existe una variante con SKU={payload.sku}.")
    v = ProductVariant(**payload.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    return serialize_variant_internal(v)


@router.put("/variants/{variant_id}")
def update_variant(
    variant_id: int,
    payload: VariantAdminUpdate,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    v = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
    if not v:
        raise HTTPException(404, "Variante no encontrada.")
    data = payload.model_dump(exclude_unset=True)
    if "sku" in data and data["sku"] != v.sku:
        if db.query(ProductVariant).filter(ProductVariant.sku == data["sku"]).first():
            raise HTTPException(409, "SKU duplicado.")
    for f, val in data.items():
        setattr(v, f, val)
    db.commit()
    db.refresh(v)
    return serialize_variant_internal(v)


@router.delete("/variants/{variant_id}", response_model=ApiMessage)
def archive_variant(
    variant_id: int,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    v = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
    if not v:
        raise HTTPException(404, "Variante no encontrada.")
    v.active = False
    db.commit()
    return ApiMessage(message="Variante archivada (inactiva).")


# -----------------------------------------------------------------------------
# Movimientos de stock (entrada manual, ajuste, salida)
# -----------------------------------------------------------------------------


@router.get("/movements", response_model=list[StockMovementPublic])
def list_movements(
    variant_id: int | None = Query(default=None),
    limit: int = Query(default=200, le=1000),
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    qry = db.query(StockMovement)
    if variant_id:
        qry = qry.filter(StockMovement.variant_id == variant_id)
    return qry.order_by(StockMovement.id.desc()).limit(limit).all()


@router.post("/movements", status_code=status.HTTP_201_CREATED)
def create_movement(
    payload: StockMovementUpsert,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
    correlation_id: str = Depends(get_correlation_id),
):
    """Registra un movimiento manual y ajusta stock:
    - entry: stock += quantity (entrada de inventario)
    - exit:  stock -= quantity (baja manual)
    - adjust: stock = max(0, stock + quantity)  -- quantity puede ser negativo
    """
    user_id = int(claims["sub"]) if claims.get("sub") else None
    v = (
        db.query(ProductVariant)
        .filter(ProductVariant.id == payload.variant_id)
        .with_for_update()
        .first()
    )
    if not v:
        raise HTTPException(404, "Variante no encontrada.")
    if payload.movement_type == "entry":
        if payload.quantity <= 0:
            raise HTTPException(422, "quantity debe ser positiva para entry.")
        v.stock += payload.quantity
    elif payload.movement_type == "exit":
        if payload.quantity <= 0:
            raise HTTPException(422, "quantity debe ser positiva para exit.")
        if v.available < payload.quantity:
            raise HTTPException(409, "Stock disponible insuficiente para la salida.")
        v.stock -= payload.quantity
    elif payload.movement_type == "adjust":
        v.stock = max(0, v.stock + payload.quantity)
    _sync_low_stock_alert(db, v)

    mv = StockMovement(
        variant_id=v.id,
        movement_type=payload.movement_type,
        quantity=payload.quantity,
        reason=payload.reason,
        user_id=user_id,
        correlation_id=correlation_id,
    )
    db.add(mv)
    db.commit()
    db.refresh(mv)
    return serialize_movement(mv)


# -----------------------------------------------------------------------------
# Alertas de stock minimo
# -----------------------------------------------------------------------------


@router.get("/alerts", response_model=list[LowStockAlertPublic])
def list_alerts(
    include_resolved: bool = Query(default=False),
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if not include_resolved:
        open_alerts = (
            db.query(LowStockAlert)
            .options(joinedload(LowStockAlert.variant))
            .filter(LowStockAlert.resolved.is_(False))
            .all()
        )
        changed = False
        for alert in open_alerts:
            if alert.variant and alert.variant.stock > alert.threshold:
                alert.resolved = True
                changed = True
        if changed:
            db.commit()

    qry = db.query(LowStockAlert).options(joinedload(LowStockAlert.variant))
    if not include_resolved:
        qry = qry.filter(LowStockAlert.resolved.is_(False))
    alerts = qry.order_by(LowStockAlert.id.desc()).all()
    product_cache: dict[int, dict | None] = {}
    return [_serialize_alert(a, product_cache) for a in alerts]


@router.post("/alerts/scan", response_model=ApiMessage)
def scan_low_stock(
    threshold: int = Query(default=5, ge=0),
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Recorre variantes y crea LowStockAlert si stock <= threshold y no hay alerta abierta."""
    low = (
        db.query(ProductVariant)
        .filter(ProductVariant.active.is_(True), ProductVariant.stock <= threshold)
        .all()
    )
    created = 0
    for v in low:
        existing = (
            db.query(LowStockAlert)
            .filter(LowStockAlert.variant_id == v.id, LowStockAlert.resolved.is_(False))
            .first()
        )
        if existing:
            continue
        db.add(LowStockAlert(
            variant_id=v.id, threshold=threshold, stock_at_alert=v.stock,
            notes=f"Stock {v.stock} <= umbral {threshold}",
        ))
        created += 1
    db.commit()
    return ApiMessage(message=f"{created} alertas nuevas (de {len(low)} variantes bajo umbral).")


@router.post("/alerts/{alert_id}/resolve", response_model=ApiMessage)
def resolve_alert(
    alert_id: int,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    a = db.query(LowStockAlert).filter(LowStockAlert.id == alert_id).first()
    if not a:
        raise HTTPException(404, "Alerta no encontrada.")
    a.resolved = True
    db.commit()
    return ApiMessage(message="Alerta marcada como resuelta.")


# -----------------------------------------------------------------------------
# Operaciones de mantenimiento (utiles para Chaos y Janitor)
# -----------------------------------------------------------------------------


@router.post("/expire-pending", response_model=ApiMessage)
def manual_expire(_: dict = Depends(require_admin)):
    """Forzar la ejecucion del scheduler de expiracion (util para Chaos tests)."""
    count = expire_pending_reservations()
    return ApiMessage(message=f"{count} reservas expiradas manualmente.")
