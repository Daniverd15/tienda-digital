from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.catalog import serialize_category, serialize_product
from app.api.dependencies import require_admin
from app.core.database import get_db
from app.models import Category, InventoryMovement, Product, ProductVariant, StoreSetting, User
from app.schemas import ApiMessage, CategoryIn, InventoryMovementIn, ProductIn, VariantIn
from app.services.audit_service import add_audit_log


router = APIRouter(prefix="/admin", tags=["Administracion catalogo"])


def serialize_variant(variant: ProductVariant) -> dict:
    return {
        "id": variant.id,
        "product_id": variant.product_id,
        "sku": variant.sku,
        "color": variant.color,
        "size": variant.size,
        "custom_attribute": variant.custom_attribute,
        "cost": float(variant.cost),
        "price": float(variant.price),
        "stock": variant.stock,
        "reserved_stock": variant.reserved_stock,
        "active": variant.active,
    }


@router.get("/categories")
def admin_categories(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [serialize_category(category) for category in db.query(Category).order_by(Category.id.desc()).all()]


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    category = Category(**payload.model_dump())
    db.add(category)
    db.flush()
    add_audit_log(db, user_id=admin.id, action="create_category", entity="categories", entity_id=category.id, new_value=payload.model_dump())
    db.commit()
    db.refresh(category)
    return serialize_category(category)


@router.get("/categories/{category_id}")
def get_category(category_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Categoria no encontrada.")
    return serialize_category(category)


@router.put("/categories/{category_id}")
def update_category(category_id: int, payload: CategoryIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Categoria no encontrada.")
    previous = serialize_category(category)
    for field, value in payload.model_dump().items():
        setattr(category, field, value)
    add_audit_log(db, user_id=admin.id, action="update_category", entity="categories", entity_id=category.id, previous_value=previous, new_value=payload.model_dump())
    db.commit()
    db.refresh(category)
    return serialize_category(category)


@router.delete("/categories/{category_id}", response_model=ApiMessage)
def archive_category(category_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Categoria no encontrada.")
    category.archived = True
    category.active = False
    add_audit_log(db, user_id=admin.id, action="archive_category", entity="categories", entity_id=category.id)
    db.commit()
    return ApiMessage(message="Categoria archivada.")


@router.get("/products")
def admin_products(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    products = db.query(Product).options(joinedload(Product.category), joinedload(Product.variants), joinedload(Product.reviews), joinedload(Product.images)).order_by(Product.id.desc()).all()
    return [serialize_product(product) for product in products]


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not db.query(Category).filter(Category.id == payload.category_id).first():
        raise HTTPException(status_code=404, detail="Categoria no encontrada.")
    product = Product(**payload.model_dump())
    db.add(product)
    db.flush()
    add_audit_log(db, user_id=admin.id, action="create_product", entity="products", entity_id=product.id, new_value=payload.model_dump())
    db.commit()
    return serialize_product(db.query(Product).options(joinedload(Product.category), joinedload(Product.variants), joinedload(Product.reviews), joinedload(Product.images)).get(product.id))


@router.get("/products/{product_id}")
def admin_product_detail(product_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    product = db.query(Product).options(joinedload(Product.category), joinedload(Product.variants), joinedload(Product.reviews), joinedload(Product.images)).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    return serialize_product(product)


@router.put("/products/{product_id}")
def update_product(product_id: int, payload: ProductIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    previous = {"name": product.name, "published": product.published, "archived": product.archived}
    for field, value in payload.model_dump().items():
        setattr(product, field, value)
    add_audit_log(db, user_id=admin.id, action="update_product", entity="products", entity_id=product.id, previous_value=previous, new_value=payload.model_dump())
    db.commit()
    product = db.query(Product).options(joinedload(Product.category), joinedload(Product.variants), joinedload(Product.reviews), joinedload(Product.images)).filter(Product.id == product_id).first()
    return serialize_product(product)


@router.delete("/products/{product_id}", response_model=ApiMessage)
def archive_product(product_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    product.archived = True
    product.published = False
    add_audit_log(db, user_id=admin.id, action="archive_product", entity="products", entity_id=product.id)
    db.commit()
    return ApiMessage(message="Producto archivado.")


@router.get("/products/{product_id}/variants")
def product_variants(product_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    variants = db.query(ProductVariant).filter(ProductVariant.product_id == product_id).order_by(ProductVariant.id.desc()).all()
    return [serialize_variant(variant) for variant in variants]


@router.post("/products/{product_id}/variants", status_code=status.HTTP_201_CREATED)
def create_variant(product_id: int, payload: VariantIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not db.query(Product).filter(Product.id == product_id).first():
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    variant = ProductVariant(product_id=product_id, **payload.model_dump())
    db.add(variant)
    db.flush()
    add_audit_log(db, user_id=admin.id, action="create_variant", entity="product_variants", entity_id=variant.id, new_value=payload.model_dump())
    db.commit()
    db.refresh(variant)
    return serialize_variant(variant)


@router.put("/products/{product_id}/variants/{variant_id}")
def update_variant(product_id: int, variant_id: int, payload: VariantIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id, ProductVariant.product_id == product_id).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Variante no encontrada.")
    previous = {"sku": variant.sku, "stock": variant.stock, "price": str(variant.price)}
    for field, value in payload.model_dump().items():
        setattr(variant, field, value)
    add_audit_log(db, user_id=admin.id, action="update_variant", entity="product_variants", entity_id=variant.id, previous_value=previous, new_value=payload.model_dump())
    db.commit()
    db.refresh(variant)
    return serialize_variant(variant)


@router.delete("/products/{product_id}/variants/{variant_id}", response_model=ApiMessage)
def deactivate_variant(product_id: int, variant_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id, ProductVariant.product_id == product_id).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Variante no encontrada.")
    variant.active = False
    add_audit_log(db, user_id=admin.id, action="deactivate_variant", entity="product_variants", entity_id=variant.id)
    db.commit()
    return ApiMessage(message="Variante desactivada.")


@router.post("/inventory/movements", status_code=status.HTTP_201_CREATED)
def create_inventory_movement(payload: InventoryMovementIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    variant = db.query(ProductVariant).filter(ProductVariant.id == payload.variant_id).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Variante no encontrada.")
    previous_stock = variant.stock
    if payload.movement_type == "entrada":
        variant.stock += payload.quantity
    elif payload.movement_type == "salida":
        if variant.stock < payload.quantity:
            raise HTTPException(status_code=409, detail="El movimiento dejaria stock negativo.")
        variant.stock -= payload.quantity
    else:
        variant.stock = payload.quantity
    movement = InventoryMovement(**payload.model_dump(), user_id=admin.id)
    db.add(movement)
    add_audit_log(db, user_id=admin.id, action="inventory_movement", entity="product_variants", entity_id=variant.id, previous_value={"stock": previous_stock}, new_value={"stock": variant.stock})
    db.commit()
    db.refresh(movement)
    return {
        "id": movement.id,
        "variant_id": movement.variant_id,
        "movement_type": movement.movement_type,
        "quantity": movement.quantity,
        "reason": movement.reason,
        "user_id": movement.user_id,
        "created_at": movement.created_at,
    }


@router.get("/inventory/alerts")
def inventory_alerts(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    settings = db.query(StoreSetting).order_by(StoreSetting.id.asc()).first()
    threshold = settings.stock_threshold if settings else 5
    variants = (
        db.query(ProductVariant)
        .options(joinedload(ProductVariant.product))
        .filter(ProductVariant.active.is_(True), ProductVariant.stock <= threshold)
        .order_by(ProductVariant.stock.asc())
        .all()
    )
    return [
        {
            "variant_id": variant.id,
            "sku": variant.sku,
            "product_name": variant.product.name,
            "stock": variant.stock,
            "threshold": threshold,
        }
        for variant in variants
    ]
