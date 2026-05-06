from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models import Category, InformativeMessage, Product, StoreSetting


router = APIRouter(tags=["Catalogo"])


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


def serialize_product(product: Product) -> dict:
    stock = sum(variant.stock for variant in product.variants if variant.active)
    visible_variants = [
        {
            "id": variant.id,
            "sku": variant.sku,
            "color": variant.color,
            "size": variant.size,
            "custom_attribute": variant.custom_attribute,
            "price": money(variant.price),
            "stock": variant.stock,
            "reserved_stock": variant.reserved_stock,
            "active": variant.active,
        }
        for variant in product.variants
        if variant.active
    ]
    return {
        "id": product.id,
        "category_id": product.category_id,
        "category_name": product.category.name if product.category else None,
        "name": product.name,
        "description": product.description,
        "long_description": product.long_description,
        "base_price": money(product.base_price),
        "published": product.published,
        "archived": product.archived,
        "image_url": product.image_url,
        "stock": stock,
        "variants": visible_variants,
    }


@router.get("/store/settings")
def get_store_settings(db: Session = Depends(get_db)):
    settings = db.query(StoreSetting).order_by(StoreSetting.id.asc()).first()
    return settings or {}


@router.get("/store/messages")
def get_store_messages(db: Session = Depends(get_db)):
    today = date.today()
    messages = (
        db.query(InformativeMessage)
        .filter(
            InformativeMessage.active.is_(True),
            (InformativeMessage.start_date.is_(None)) | (InformativeMessage.start_date <= today),
            (InformativeMessage.end_date.is_(None)) | (InformativeMessage.end_date >= today),
        )
        .order_by(InformativeMessage.id.desc())
        .all()
    )
    return messages


@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    categories = (
        db.query(Category)
        .filter(Category.active.is_(True), Category.archived.is_(False))
        .order_by(Category.name.asc())
        .all()
    )
    return [serialize_category(category) for category in categories]


@router.get("/products")
def get_products(db: Session = Depends(get_db)):
    products = (
        db.query(Product)
        .options(joinedload(Product.category), joinedload(Product.variants))
        .join(Category)
        .filter(
            Product.published.is_(True),
            Product.archived.is_(False),
            Category.active.is_(True),
            Category.archived.is_(False),
        )
        .order_by(Product.created_at.desc())
        .all()
    )
    return [serialize_product(product) for product in products]

