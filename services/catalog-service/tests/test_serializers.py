"""Tests unitarios de serializadores y cache (no requieren MySQL)."""
from types import SimpleNamespace

from app.services.serializers import money, serialize_product_summary, serialize_product_detail


class FakeRating(SimpleNamespace):
    pass


class FakeCategory(SimpleNamespace):
    pass


class FakeProduct(SimpleNamespace):
    pass


class FakeImage(SimpleNamespace):
    pass


def _fake_product(**overrides):
    base = dict(
        id=1, category_id=10, name="Camiseta", description="basica",
        long_description="larga", base_price=49000, image_url="x.jpg",
        published=True, archived=False,
        category=FakeCategory(id=10, name="Ropa"),
        images=[FakeImage(id=99, image_url="g.jpg", alt_text="alt")],
        rating=FakeRating(average=4.5, count=2),
    )
    base.update(overrides)
    return FakeProduct(**base)


def test_money_handles_none_and_decimal():
    assert money(None) == 0.0
    assert money(123) == 123.0
    assert money(45.6) == 45.6


def test_summary_uses_rating_when_present():
    p = _fake_product()
    out = serialize_product_summary(p)
    assert out["id"] == 1
    assert out["category_name"] == "Ropa"
    assert out["base_price"] == 49000.0
    assert out["average_rating"] == 4.5
    assert out["reviews_count"] == 2


def test_summary_handles_no_rating():
    p = _fake_product(rating=None)
    out = serialize_product_summary(p)
    assert out["average_rating"] == 0.0
    assert out["reviews_count"] == 0


def test_detail_includes_gallery_and_variants_passthrough():
    p = _fake_product()
    variants = [{"id": 1, "sku": "SKU-1", "stock": 5}]
    out = serialize_product_detail(p, variants=variants, inventory_available=True)
    assert out["gallery"][0]["image_url"] == "g.jpg"
    assert out["variants"] == variants
    assert out["inventory_available"] is True


def test_detail_marks_inventory_unavailable():
    p = _fake_product()
    out = serialize_product_detail(p, variants=[], inventory_available=False)
    assert out["variants"] == []
    assert out["inventory_available"] is False
