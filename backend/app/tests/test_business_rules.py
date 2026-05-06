from decimal import Decimal
from types import SimpleNamespace

from app.api.orders import calculate_cart_totals


def test_net_total_never_goes_negative_when_discount_exceeds_subtotal():
    cart = SimpleNamespace(items=[SimpleNamespace(unit_price=Decimal("1000"), quantity=1)])
    totals = calculate_cart_totals(cart, discount=Decimal("2000"), additional_costs=Decimal("0"))
    assert totals["total"] == Decimal("0")


def test_checkout_total_adds_costs_and_discount():
    cart = SimpleNamespace(items=[SimpleNamespace(unit_price=Decimal("50000"), quantity=2)])
    totals = calculate_cart_totals(cart, discount=Decimal("10000"), additional_costs=Decimal("7000"))
    assert totals["subtotal"] == Decimal("100000")
    assert totals["total"] == Decimal("97000")

