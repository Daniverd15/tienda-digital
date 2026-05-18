from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models import Category, InformativeMessage, Product, ProductImage, Review, StoreSetting


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
    ratings = [review.rating for review in product.reviews if review.approved]
    average_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0
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
        "gallery": [
            {"id": image.id, "image_url": image.image_url, "alt_text": image.alt_text}
            for image in product.images
        ],
        "stock": stock,
        "average_rating": average_rating,
        "reviews_count": len(ratings),
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
        .options(joinedload(Product.category), joinedload(Product.variants), joinedload(Product.reviews), joinedload(Product.images))
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


@router.get("/products/search")
def search_products(
    q: str | None = Query(default=None),
    category_id: int | None = Query(default=None),
    min_price: float | None = Query(default=None),
    max_price: float | None = Query(default=None),
    in_stock: bool | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Product)
        .options(joinedload(Product.category), joinedload(Product.variants), joinedload(Product.reviews), joinedload(Product.images))
        .join(Category)
        .filter(
            Product.published.is_(True),
            Product.archived.is_(False),
            Category.active.is_(True),
            Category.archived.is_(False),
        )
    )
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter((Product.name.ilike(pattern)) | (Product.description.ilike(pattern)))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if min_price is not None:
        query = query.filter(Product.base_price >= min_price)
    if max_price is not None:
        query = query.filter(Product.base_price <= max_price)
    products = query.order_by(Product.name.asc()).all()
    if in_stock is True:
        products = [product for product in products if sum(variant.stock for variant in product.variants if variant.active) > 0]
    return [serialize_product(product) for product in products]


@router.get("/products/{product_id}")
def get_product_detail(product_id: int, db: Session = Depends(get_db)):
    product = (
        db.query(Product)
        .options(joinedload(Product.category), joinedload(Product.variants), joinedload(Product.reviews), joinedload(Product.images))
        .filter(Product.id == product_id, Product.published.is_(True), Product.archived.is_(False))
        .first()
    )
    if not product or product.category.archived or not product.category.active:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    return serialize_product(product)


@router.get("/products/{product_id}/reviews")
def get_product_reviews(product_id: int, db: Session = Depends(get_db)):
    product_exists = db.query(func.count(Product.id)).filter(Product.id == product_id).scalar()
    if not product_exists:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    reviews = (
        db.query(Review)
        .filter(Review.product_id == product_id, Review.approved.is_(True))
        .order_by(Review.created_at.desc())
        .all()
    )
    return [
        {
            "id": review.id,
            "rating": review.rating,
            "comment": review.comment,
            "user_name": review.user.name if review.user else "Cliente",
            "created_at": review.created_at,
        }
        for review in reviews
    ]
