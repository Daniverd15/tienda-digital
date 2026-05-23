"""Conversion de modelos ORM a diccionarios para respuesta JSON."""
from decimal import Decimal

from app.models import Category, Product, ProductImage


def money(value: Decimal | int | float | None) -> float:
    """Convierte importes a float para respuestas JSON estables."""
    return float(value or 0)


def serialize_category(category: Category) -> dict:
    """Normaliza categorias para vistas publicas y administrativas."""
    return {
        "id": category.id,
        "name": category.name,
        "description": category.description,
        "active": category.active,
        "archived": category.archived,
    }


def serialize_image(image: ProductImage) -> dict:
    """Serializa una imagen de galeria con texto alternativo."""
    return {"id": image.id, "image_url": image.image_url, "alt_text": image.alt_text}


def serialize_product_summary(product: Product, stock_info: dict | None = None,
                              inventory_available: bool = True) -> dict:
    """Convierte el producto en dict para el listado publico.

    `stock_info` es la entrada del stock-summary de Inventory para este producto
    (puede ser None si el producto no tiene variantes o si Inventory esta caido).
    `inventory_available` indica si Inventory respondio: cuando es False el
    frontend NO debe pintar "AGOTADO" porque no es informacion confiable.
    """
    rating = product.rating
    stock_info = stock_info or {}
    stock_total = int(stock_info.get("stock", 0))
    variant_count = int(stock_info.get("variant_count", 0))
    return {
        "id": product.id,
        "category_id": product.category_id,
        "category_name": product.category.name if product.category else None,
        "name": product.name,
        "description": product.description,
        "base_price": money(product.base_price),
        "image_url": product.image_url,
        "published": product.published,
        "archived": product.archived,
        "average_rating": rating.average if rating else 0.0,
        "reviews_count": rating.count if rating else 0,
        # Stock real (agregado desde Inventory)
        "stock": stock_total,
        "variant_count": variant_count,
        "inventory_available": inventory_available,
    }


def serialize_product_detail(
    product: Product, variants: list[dict] | None = None, inventory_available: bool = True
) -> dict:
    """Construye la ficha completa de producto uniendo catalogo e inventario."""
    rating = product.rating
    return {
        "id": product.id,
        "category_id": product.category_id,
        "category_name": product.category.name if product.category else None,
        "name": product.name,
        "description": product.description,
        "long_description": product.long_description,
        "base_price": money(product.base_price),
        "image_url": product.image_url,
        "published": product.published,
        "archived": product.archived,
        "gallery": [serialize_image(img) for img in product.images],
        "average_rating": rating.average if rating else 0.0,
        "reviews_count": rating.count if rating else 0,
        "variants": variants or [],
        "inventory_available": inventory_available,
    }
