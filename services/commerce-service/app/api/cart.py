"""Endpoints del carrito del cliente.

================================================================================
PROPOSITO
================================================================================
Gestiona el carrito de compras antes del checkout. Cada usuario autenticado
tiene UN unico carrito en estado "open" a la vez. Cuando hace checkout, el
carrito se marca como "checked_out" y se crea uno nuevo en la proxima visita.

Endpoints:
  GET    /cart                → devuelve el carrito actual (o lo crea vacio)
  POST   /cart/items          → agrega una variante al carrito
  PUT    /cart/items/{id}     → cambia la cantidad de un item
  DELETE /cart/items/{id}     → elimina un item
  DELETE /cart                → vacia el carrito completo

================================================================================
SNAPSHOT DE PRODUCTOS
================================================================================
Al agregar un item, se "congelan" en el CartItem el product_name, descripcion,
precio e imagen. Esto evita que:
  - Si el admin cambia el precio mientras el cliente esta comprando, el
    precio del carrito no cambia (el cliente paga lo que vio).
  - Si el producto se borra, el carrito sigue mostrando los datos.

El precio del CartItem se valida AL HACER CHECKOUT contra Inventory por si
hubo desfases. Sin embargo, la validacion de stock SI es en tiempo real
(cada GET /cart consulta Inventory para mostrar available_stock actualizado).
"""
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
    """Devuelve el carrito "open" del usuario, creandolo si no existe.

    Politica: un usuario tiene EXACTAMENTE un carrito en estado "open" a la vez.
    Cuando hace checkout, ese carrito pasa a "checked_out" y la proxima
    llamada a esta funcion crea uno nuevo.
    """
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
    """Convierte el Cart de SQLAlchemy a dict listo para JSON.

    Para CADA item del carrito consulta Inventory en tiempo real para
    obtener `available_stock` actualizado y un flag `has_enough_stock`
    que el frontend usa para mostrar advertencias visuales (ej. "ya no
    hay suficiente stock para esta cantidad").

    Esto produce N llamadas a Inventory por GET /cart, lo que es aceptable
    porque el carrito tipicamente tiene pocos items. En una evolucion
    futura podriamos usar el endpoint batch /variants/by-ids.
    """
    items = []
    for i in cart.items:
        # Consulta a Inventory (puede devolver None si Inventory cae o la
        # variante fue borrada).
        variant = inventory_get_variant(i.variant_id)
        available_stock = None
        is_active = False
        if variant:
            available_stock = int(variant.get("available", 0))
            is_active = bool(variant.get("active", False))

        # Calculo del total de la linea: unit_price (snapshot) x quantity.
        unit_price = float(i.unit_price)
        total = unit_price * i.quantity
        items.append({
            "id": i.id, "variant_id": i.variant_id, "product_id": i.product_id,
            "product_name": i.product_name, "variant_description": i.variant_description,
            "image_url": i.image_url, "quantity": i.quantity, "unit_price": unit_price,
            # SKU se trae de Inventory en tiempo real (no se snapshotea
            # porque el admin puede cambiarlo y queremos mostrar el actual).
            "sku": variant.get("sku") if variant else None,
            "total": total, "available_stock": available_stock,
            # Flag conveniente para el frontend: True si hay stock para
            # la cantidad actual del item. Si Inventory cae, queda False.
            "has_enough_stock": is_active and available_stock is not None and available_stock >= i.quantity,
        })
    # Subtotal = suma de todas las lineas. No incluye descuentos ni envio
    # (esos se aplican en el checkout).
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
    """Devuelve el carrito actual del usuario autenticado (o uno vacio si no tiene).

    Idempotente: llamarlo N veces da el mismo resultado. Si el carrito no
    existe lo crea vacio en BD.
    """
    cart = _get_or_create_cart(db, user_id)
    return _serialize_cart(cart)


@router.post("/items", status_code=status.HTTP_201_CREATED)
def add_item(
    payload: CartItemAdd,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
    _: str = Depends(get_correlation_id),
):
    """Agrega una variante al carrito (o suma cantidad si ya esta).

    Flujo:
    1. Validar que la variante exista y este activa (consulta Inventory).
    2. Validar que haya stock suficiente.
    3. Snapshotear el producto desde Catalog (nombre, imagen).
    4. Si ya hay un CartItem con esa variante → sumar cantidad (verificando stock).
       Si no → crear uno nuevo con el precio actual.
    """
    # ─── 1. Validar variante (existe + activa) ──────────────────────────
    variant = inventory_get_variant(payload.variant_id)
    if not variant:
        raise HTTPException(422, f"Variante {payload.variant_id} no existe o esta inactiva.")
    if not variant.get("active", False):
        raise HTTPException(422, f"Variante {payload.variant_id} esta inactiva.")
    # ─── 2. Validar stock suficiente ────────────────────────────────────
    if variant.get("available", 0) < payload.quantity:
        raise HTTPException(409, f"Stock insuficiente. Disponible: {variant.get('available', 0)}")

    # ─── 3. Snapshot del producto desde Catalog ─────────────────────────
    # Necesitamos nombre + imagen para guardarlos en el CartItem.
    product = catalog_get_product(variant["product_id"])
    if not product:
        raise HTTPException(422, "Producto no encontrado en catalogo.")

    cart = _get_or_create_cart(db, user_id)
    # Verificar si la variante ya esta en el carrito (UNIQUE constraint
    # en (cart_id, variant_id) garantiza que no haya duplicados).
    existing = (
        db.query(CartItem)
        .filter(CartItem.cart_id == cart.id, CartItem.variant_id == payload.variant_id)
        .first()
    )
    if existing:
        # Sumamos a la cantidad existente. Validamos stock OTRA VEZ porque
        # ahora pedimos (existing + nueva), que puede exceder el disponible.
        new_qty = existing.quantity + payload.quantity
        if new_qty > variant.get("available", 0):
            raise HTTPException(409, f"Stock insuficiente para esa cantidad acumulada.")
        existing.quantity = new_qty
    else:
        # Creamos un CartItem nuevo con SNAPSHOT del precio y datos.
        # Variant_description = "Color / Talla / Atributo" para mostrar en
        # el carrito al cliente (ej. "Negro / M").
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
    """Cambia la cantidad de un item del carrito. Valida stock antes de aplicar.

    Devuelve 404 si el item no pertenece al carrito del usuario (defensa
    contra IDOR: un usuario no puede manipular items de otro).
    """
    cart = _get_or_create_cart(db, user_id)
    # Filtro por cart_id ademas de item_id: asegura que el item pertenece al
    # carrito del usuario autenticado.
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.cart_id == cart.id).first()
    if not item:
        raise HTTPException(404, "Item no encontrado en tu carrito.")
    # Validar que haya stock para la NUEVA cantidad.
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
    """Elimina un item especifico del carrito."""
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
    """Vacia el carrito completo (elimina todos sus items).

    El Cart en si NO se borra (queda en status="open" sin items). La
    proxima llamada a GET /cart devuelve un carrito vacio sin crear uno nuevo.
    """
    cart = _get_or_create_cart(db, user_id)
    # Iteramos sobre list() del relationship para evitar problemas de
    # modificacion de coleccion durante iteracion.
    for item in list(cart.items):
        db.delete(item)
    db.commit()
    return ApiMessage(message="Carrito vaciado.")
