"""Rutas del carrito de compras en el monolito legacy.

Gestiona el carrito abierto por usuario: lectura, agregado, actualizacion,
eliminacion y validacion de stock antes del checkout. En microservicios esta
logica se separa hacia Commerce Service, que coordina carrito y SAGA de pago.
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import require_customer
from app.core.database import get_db
from app.models import Cart, CartItem, ProductVariant, User
from app.schemas import ApiMessage, CartItemIn, CartItemUpdate
from app.services.audit_service import add_audit_log


router = APIRouter(prefix="/cart", tags=["Carrito"])


def get_open_cart(db: Session, user_id: int) -> Cart:
    """Obtiene el carrito abierto del usuario o crea uno si aun no existe."""
    cart = (
        db.query(Cart)
        .options(joinedload(Cart.items).joinedload(CartItem.variant).joinedload(ProductVariant.product))
        .filter(Cart.user_id == user_id, Cart.status == "open")
        .first()
    )
    if not cart:
        cart = Cart(user_id=user_id, status="open")
        db.add(cart)
        db.flush()
    return cart


def serialize_cart(cart: Cart) -> dict:
    """Convierte el carrito ORM a JSON estable para la SPA."""
    items = []
    subtotal = Decimal("0")
    for item in cart.items:
        line_total = Decimal(item.unit_price) * item.quantity
        subtotal += line_total
        variant = item.variant
        product = variant.product
        items.append(
            {
                "id": item.id,
                "variant_id": item.variant_id,
                "product_id": product.id,
                "product_name": product.name,
                "variant_description": " / ".join(
                    part for part in [variant.color, variant.size, variant.custom_attribute] if part
                )
                or variant.sku,
                "sku": variant.sku,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "total": float(line_total),
                "available_stock": variant.stock,
                "image_url": product.image_url,
            }
        )
    return {"id": cart.id, "status": cart.status, "items": items, "subtotal": float(subtotal)}


def validate_variant(db: Session, variant_id: int, quantity: int) -> ProductVariant:
    """Valida que la variante exista, este activa/publicada y tenga stock."""
    variant = (
        db.query(ProductVariant)
        .options(joinedload(ProductVariant.product))
        .filter(ProductVariant.id == variant_id, ProductVariant.active.is_(True))
        .first()
    )
    if not variant or not variant.product.published or variant.product.archived:
        raise HTTPException(status_code=404, detail="Variante no disponible.")
    if variant.stock < quantity:
        raise HTTPException(status_code=409, detail="Stock insuficiente para la variante seleccionada.")
    return variant


@router.get("")
def read_cart(current_user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Devuelve el carrito actual del cliente autenticado."""
    cart = get_open_cart(db, current_user.id)
    db.commit()
    db.refresh(cart)
    return serialize_cart(cart)


@router.post("/items", status_code=status.HTTP_201_CREATED)
def add_item(payload: CartItemIn, current_user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Agrega una variante al carrito o incrementa su cantidad existente."""
    cart = get_open_cart(db, current_user.id)
    variant = validate_variant(db, payload.variant_id, payload.quantity)
    item = next((cart_item for cart_item in cart.items if cart_item.variant_id == payload.variant_id), None)
    new_quantity = payload.quantity + (item.quantity if item else 0)
    if variant.stock < new_quantity:
        raise HTTPException(status_code=409, detail="La cantidad total excede el stock disponible.")
    if item:
        item.quantity = new_quantity
        item.unit_price = variant.price
    else:
        db.add(CartItem(cart_id=cart.id, variant_id=variant.id, quantity=payload.quantity, unit_price=variant.price))
    add_audit_log(db, user_id=current_user.id, action="add_cart_item", entity="cart_items", entity_id=variant.id)
    db.commit()
    cart = get_open_cart(db, current_user.id)
    return serialize_cart(cart)


@router.put("/items/{item_id}")
def update_item(
    item_id: int,
    payload: CartItemUpdate,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Cambia la cantidad de un item validando disponibilidad actual."""
    cart = get_open_cart(db, current_user.id)
    item = next((cart_item for cart_item in cart.items if cart_item.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado.")
    validate_variant(db, item.variant_id, payload.quantity)
    previous = {"quantity": item.quantity}
    item.quantity = payload.quantity
    add_audit_log(
        db,
        user_id=current_user.id,
        action="update_cart_item",
        entity="cart_items",
        entity_id=item.id,
        previous_value=previous,
        new_value={"quantity": payload.quantity},
    )
    db.commit()
    cart = get_open_cart(db, current_user.id)
    return serialize_cart(cart)


@router.delete("/items/{item_id}", response_model=ApiMessage)
def delete_item(item_id: int, current_user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Quita un item del carrito abierto del usuario."""
    cart = get_open_cart(db, current_user.id)
    item = next((cart_item for cart_item in cart.items if cart_item.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado.")
    db.delete(item)
    add_audit_log(db, user_id=current_user.id, action="delete_cart_item", entity="cart_items", entity_id=item_id)
    db.commit()
    return ApiMessage(message="Item eliminado del carrito.")


@router.post("/validate-stock")
def validate_stock(current_user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Revisa el carrito completo antes del checkout y reporta faltantes."""
    cart = get_open_cart(db, current_user.id)
    errors = [
        {
            "item_id": item.id,
            "variant_id": item.variant_id,
            "requested": item.quantity,
            "available": item.variant.stock,
        }
        for item in cart.items
        if item.quantity > item.variant.stock
    ]
    return {"valid": len(errors) == 0, "errors": errors}
