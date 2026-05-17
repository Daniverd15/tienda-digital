"""Conversion de modelos ORM a diccionarios para respuesta JSON."""
from decimal import Decimal

from app.models import Category, Product, ProductImage


def money(value: Decimal | int | float | None) -> float:
    return float(value or 0)


def serialize_category(category: Category) -> dict:
    return {
        "id": category.id,
        "name": category.name,
        "description": category.description,
        "active": category.active,
        "archived": category.archived,
    }


def serialize_image(image: ProductImage) -> dict:
    return {"id": image.id, "image_url": image.image_url, "alt_text": image.alt_text}


def serialize_product_summary(product: Product) -> dict:
    rating = product.rating
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
    }


def serialize_product_detail(
    product: Product, variants: list[dict] | None = None, inventory_available: bool = True
) -> dict:
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
