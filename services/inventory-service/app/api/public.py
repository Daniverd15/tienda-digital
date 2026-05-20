"""Endpoints publicos de Inventory.

Consumidos por Catalog (para enriquecer detalle de producto con variantes y
stock) y por el frontend (para mostrar disponibilidad).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import ProductVariant
from app.services.serializers import serialize_variant_public


router = APIRouter(tags=["Inventario publico"])


@router.get("/products/{product_id}/variants")
def get_variants_by_product(product_id: int, db: Session = Depends(get_db)):
    """Listado de variantes activas de un producto. Si no hay, devuelve 404
    (Catalog interpreta como 'sin variantes registradas')."""
    variants = (
        db.query(ProductVariant)
        .filter(ProductVariant.product_id == product_id, ProductVariant.active.is_(True))
        .order_by(ProductVariant.id.asc())
        .all()
    )
    if not variants:
        raise HTTPException(404, "Producto sin variantes registradas.")
    return [serialize_variant_public(v) for v in variants]


@router.get("/variants/by-ids")
def variants_by_ids(ids: str = Query(..., description="ids separados por coma"),
                    db: Session = Depends(get_db)):
    """Detalle (publico) de variantes por ids, util para Commerce al calcular COGS.

    NOTA: este endpoint DEBE declararse antes que /variants/{variant_id}
    porque FastAPI matchea en orden y "by-ids" no es un int valido.
    """
    try:
        id_list = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(422, "ids debe ser una lista separada por coma de enteros.")
    if not id_list:
        return []
    rows = db.query(ProductVariant).filter(ProductVariant.id.in_(id_list)).all()
    return [
        {
            "id": v.id,
            "product_id": v.product_id,
            "sku": v.sku,
            "color": v.color,
            "color_hex": v.color_hex,
            "size": v.size,
            "cost": float(v.cost or 0),
            "price": float(v.price or 0),
        }
        for v in rows
    ]


@router.get("/variants/{variant_id}")
def get_variant(variant_id: int, db: Session = Depends(get_db)):
    v = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
    if not v:
        raise HTTPException(404, "Variante no encontrada.")
    return serialize_variant_public(v)


@router.get("/stock-summary")
def stock_summary(db: Session = Depends(get_db)):
    """Agregado de stock disponible por producto.

    Devuelve `{ product_id (str): {"stock": int, "variant_count": int, "min_price": float, "max_price": float} }`.
    Usado por Catalog para enriquecer el listado de productos con disponibilidad
    real sin tener que llamar variant-per-variant.
    """
    rows = (
        db.query(
            ProductVariant.product_id,
            func.coalesce(func.sum(ProductVariant.stock - ProductVariant.reserved_stock), 0),
            func.count(ProductVariant.id),
            func.min(ProductVariant.price),
            func.max(ProductVariant.price),
        )
        .filter(ProductVariant.active.is_(True))
        .group_by(ProductVariant.product_id)
        .all()
    )
    return {
        str(pid): {
            "stock": int(stock or 0),
            "variant_count": int(count or 0),
            "min_price": float(min_p or 0),
            "max_price": float(max_p or 0),
        }
        for pid, stock, count, min_p, max_p in rows
    }


