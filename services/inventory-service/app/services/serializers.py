"""Conversion ORM -> JSON."""
from decimal import Decimal

from app.models import ProductVariant, StockMovement


def money(v: Decimal | int | float | None) -> float:
    return float(v or 0)


def serialize_variant_public(v: ProductVariant) -> dict:
    return {
        "id": v.id,
        "product_id": v.product_id,
        "sku": v.sku,
        "color": v.color,
        "size": v.size,
        "custom_attribute": v.custom_attribute,
        "price": money(v.price),
        "available": v.available,
        "active": v.active,
    }


def serialize_variant_internal(v: ProductVariant) -> dict:
    return {
        "id": v.id,
        "product_id": v.product_id,
        "sku": v.sku,
        "color": v.color,
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
