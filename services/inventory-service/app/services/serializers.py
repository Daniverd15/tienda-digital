"""Conversion ORM -> JSON."""
from decimal import Decimal

from app.models import ProductVariant, StockMovement


def money(v: Decimal | int | float | None) -> float:
    """Convierte valores monetarios Decimal a float para JSON."""
    return float(v or 0)


def serialize_variant_public(v: ProductVariant) -> dict:
    """Serializa una variante sin exponer costo ni stock interno."""
    return {
        "id": v.id,
        "product_id": v.product_id,
        "sku": v.sku,
        "color": v.color,
        "color_hex": v.color_hex,
        "size": v.size,
        "custom_attribute": v.custom_attribute,
        "price": money(v.price),
        "available": v.available,
        "active": v.active,
    }


def serialize_variant_internal(v: ProductVariant) -> dict:
    """Serializa una variante completa para administracion e integraciones."""
    return {
        "id": v.id,
        "product_id": v.product_id,
        "sku": v.sku,
        "color": v.color,
        "color_hex": v.color_hex,
        "size": v.size,
        "custom_attribute": v.custom_attribute,
        "cost": money(v.cost),
        "price": money(v.price),
        "stock": v.stock,
        "reserved_stock": v.reserved_stock,
        "available": v.available,
        "active": v.active,
        "created_at": v.created_at.isoformat(),
        "updated_at": v.updated_at.isoformat(),
    }


def serialize_movement(m: StockMovement) -> dict:
    """Serializa movimientos de stock para auditoria de inventario."""
    return {
        "id": m.id,
        "variant_id": m.variant_id,
        "movement_type": m.movement_type,
        "quantity": m.quantity,
        "reason": m.reason,
        "user_id": m.user_id,
        "order_id": m.order_id,
        "correlation_id": m.correlation_id,
        "created_at": m.created_at.isoformat(),
    }
