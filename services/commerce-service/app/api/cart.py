"""Endpoints del carrito del cliente."""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import current_user_id, get_correlation_id
from app.models import Cart, CartItem
from app.schemas import ApiMessage, CartItemAdd, CartItemUpdate, CartPublic
from app.services.http_clients import catalog_get_product, inventory_get_variant


router = APIRouter(prefix="/cart", tags=["Carrito"])


def _get_or_create_cart(db: Session, user_id: int) -> Cart:
    cart = (
        db.query(Cart)
        .filter(Cart.user_id == user_id, Cart.status == "open")
        .first()
    )
    if not cart:
        cart = Cart(user_id=user_id, status="open")
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart


def _serialize_cart(cart: Cart) -> dict:
    items = [{
        "id": i.id, "variant_id": i.variant_id, "product_id": i.product_id,
        "product_name": i.product_name, "variant_description": i.variant_description,
        "image_url": i.image_url, "quantity": i.quantity, "unit_price": float(i.unit_price),
    } for i in cart.items]
    subtotal = sum(i["quantity"] * i["unit_price"] for i in items)
    return {
        "id": cart.id, "user_id": cart.user_id, "status": cart.status,
        "items": items, "subtotal": float(subtotal),
        "item_count": sum(i["quantity"] for i in items),
    }


@router.get("")
def get_cart(
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    cart = _get_or_create_cart(db, user_id)
    return _serialize_cart(cart)


@router.post("/items", status_code=status.HTTP_201_CREATED)
def add_item(
    payload: CartItemAdd,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
    _: str = Depends(get_correlation_id),
):
    # 1. validar variante existe y esta activa (consulta a Inventory)
    variant = inventory_get_variant(payload.variant_id)
    if not variant:
        raise HTTPException(422, f"Variante {payload.variant_id} no existe o esta inactiva.")
    if not variant.get("active", False):
        raise HTTPException(422, f"Variante {payload.variant_id} esta inactiva.")
    if variant.get("available", 0) < payload.quantity:
        raise HTTPException(409, f"Stock insuficiente. Disponible: {variant.get('available', 0)}")

    # 2. snapshot de producto (consulta a Catalog)
    product = catalog_get_product(variant["product_id"])
    if not product:
        raise HTTPException(422, "Producto no encontrado en catalogo.")

    cart = _get_or_create_cart(db, user_id)
    existing = (
        db.query(CartItem)
        .filter(CartItem.cart_id == cart.id, CartItem.variant_id == payload.variant_id)
        .first()
    )
    if existing:
        new_qty = existing.quantity + payload.quantity
        if new_qty > variant.get("available", 0):
            raise HTTPException(409, f"Stock insuficiente para esa cantidad acumulada.")
        existing.quantity = new_qty
    else:
        description = " / ".join(
            x for x in [variant.get("color"), variant.get("size"), variant.get("custom_attribute")]
            if x
        ) or variant["sku"]
        db.add(CartItem(
            cart_id=cart.id,
            variant_id=payload.variant_id,
            product_id=variant["product_id"],
            product_name=product["name"],
            variant_description=description,
            image_url=product.get("image_url"),
            quantity=payload.quantity,
            unit_price=Decimal(str(variant["price"])),
        ))
    db.commit()
    db.refresh(cart)
    return _serialize_cart(cart)


@router.put("/items/{item_id}")
def update_item(
    item_id: int,
    payload: CartItemUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    cart = _get_or_create_cart(db, user_id)
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.cart_id == cart.id).first()
    if not item:
        raise HTTPException(404, "Item no encontrado en tu carrito.")
    variant = inventory_get_variant(item.variant_id)
    if variant and variant.get("available", 0) < payload.quantity:
        raise HTTPException(409, f"Stock insuficiente. Disponible: {variant.get('available', 0)}")
    item.quantity = payload.quantity
    db.commit()
    db.refresh(cart)
    return _serialize_cart(cart)


@router.delete("/items/{item_id}", response_model=ApiMessage)
def remove_item(
    item_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    cart = _get_or_create_cart(db, user_id)
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.cart_id == cart.id).first()
    if not item:
        raise HTTPException(404, "Item no encontrado.")
    db.delete(item)
    db.commit()
    return ApiMessage(message="Item eliminado del carrito.")


@router.delete("", response_model=ApiMessage)
def clear_cart(
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    cart = _get_or_create_cart(db, user_id)
    for item in list(cart.items):
        db.delete(item)
    db.commit()
    return ApiMessage(message="Carrito vaciado.")
