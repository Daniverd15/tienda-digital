"""Tests unitarios de serializers."""
from types import SimpleNamespace
from datetime import datetime

from app.services.serializers import money, serialize_variant_public, serialize_variant_internal


def _v(**ov):
    """Construye una variante falsa con defaults editables por prueba."""
    base = dict(
        id=1, product_id=10, sku="SKU-1", color="negro", size="M",
        custom_attribute=None, cost=20000, price=49000, stock=10,
        reserved_stock=2, active=True,
        created_at=datetime(2026, 5, 17), updated_at=datetime(2026, 5, 17),
        available=8,
    )
    base.update(ov)
    return SimpleNamespace(**base)


def test_money_handles_none():
    """money convierte None y numeros a float consistente."""
    assert money(None) == 0.0
    assert money(123) == 123.0


def test_variant_public_no_revela_cost_ni_stock():
    """La vista publica oculta costo, stock total y reservado."""
    out = serialize_variant_public(_v())
    assert out["available"] == 8
    assert "cost" not in out
    assert "stock" not in out
    assert "reserved_stock" not in out


def test_variant_internal_revela_todo():
    """La vista interna conserva campos sensibles para administracion."""
    out = serialize_variant_internal(_v())
    assert out["cost"] == 20000.0
    assert out["stock"] == 10
    assert out["reserved_stock"] == 2
    assert out["available"] == 8
