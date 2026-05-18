"""Endpoints publicos de Inventory.

Consumidos por Catalog (para enriquecer detalle de producto con variantes y
stock) y por el frontend (para mostrar disponibilidad).
"""
from fastapi import APIRouter, Depends, HTTPException
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


@router.get("/variants/{variant_id}")
def get_variant(variant_id: int, db: Session = Depends(get_db)):
    v = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
    if not v:
        raise HTTPException(404, "Variante no encontrada.")
    return serialize_variant_public(v)
