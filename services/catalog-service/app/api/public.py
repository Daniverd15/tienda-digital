"""Endpoints publicos del Catalog Service.

================================================================================
PROPOSITO
================================================================================
Sirven el catalogo de la tienda al frontend SIN requerir autenticacion.
Cualquier visitante (autenticado o no) puede:

  GET /catalog          → overview (settings + mensajes + categorias + destacados)
  GET /store/settings   → identidad visual de la tienda (logo, colores)
  GET /store/messages   → mensajes informativos activos
  GET /categories       → categorias activas y no archivadas
  GET /products         → listado de productos con filtros (q, category_id, precio)
  GET /products/{id}    → detalle de producto + variantes enriquecidas

================================================================================
PATRON CACHE-ASIDE
================================================================================
Cada endpoint:
  1. Intenta leer desde Redis con una clave derivada de los parametros.
  2. Si HIT → devuelve el cached (latencia <1ms).
  3. Si MISS → consulta MySQL, serializa el resultado, lo guarda en Redis
     con TTL apropiado y devuelve.

TTLs configurados:
  - SETTINGS:        300s (cambia poco — solo cuando admin edita la tienda)
  - CATEGORIES:      300s (idem)
  - PRODUCTS_LIST:    60s (stock cambia con cada compra)
  - PRODUCT_DETAIL:   60s (stock + variantes pueden cambiar)

Cuando admin edita algo, los endpoints /admin/* llaman a cache.invalidate_prefix()
para invalidar las claves afectadas inmediatamente (no esperan al TTL).

Si Redis cae: todos los GET caen a MySQL (modo degradado).

================================================================================
ENRIQUECIMIENTO CON INVENTORY
================================================================================
GET /products llama a Inventory.get_stock_summary() para enriquecer cada
producto con `stock` y `variant_count`. Si Inventory cae, los productos se
devuelven con `inventory_available=False` y el frontend muestra "Consultar"
en vez de "AGOTADO" (no engañar al cliente con info no confiable).
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core import cache
from app.core.database import get_db
from app.models import Category, InformativeMessage, Product, StoreSetting
from app.services.inventory_client import get_stock_summary, get_variants_for_product
from app.services.serializers import (
    serialize_category,
    serialize_product_detail,
    serialize_product_summary,
)


router = APIRouter(tags=["Catalogo"])

CACHE_TTL_SETTINGS = 300
CACHE_TTL_CATEGORIES = 300
CACHE_TTL_PRODUCTS_LIST = 60
CACHE_TTL_PRODUCT_DETAIL = 60


# -----------------------------------------------------------------------------
# Store settings & mensajes (lecturas masivas, TTL alto)
# -----------------------------------------------------------------------------


@router.get("/store/settings")
def store_settings(db: Session = Depends(get_db)):
    cached = cache.get("catalog:store:settings")
    if cached is not None:
        return cached
    s = db.query(StoreSetting).order_by(StoreSetting.id.asc()).first()
    if not s:
        return {}
    data = {
        "id": s.id,
        "commercial_name": s.commercial_name,
        "logo_url": s.logo_url,
        "primary_color": s.primary_color,
        "secondary_color": s.secondary_color,
        "banner_url": s.banner_url,
        "contact_email": s.contact_email,
        "contact_phone": s.contact_phone,
        "currency": s.currency,
        "stock_threshold": s.stock_threshold,
    }
    cache.set_("catalog:store:settings", data, CACHE_TTL_SETTINGS)
    return data


@router.get("/store/messages")
def store_messages(db: Session = Depends(get_db)):
    today = date.today().isoformat()
    cache_key = f"catalog:store:messages:{today}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    today_d = date.today()
    rows = (
        db.query(InformativeMessage)
        .filter(
            InformativeMessage.active.is_(True),
            or_(InformativeMessage.start_date.is_(None), InformativeMessage.start_date <= today_d),
            or_(InformativeMessage.end_date.is_(None), InformativeMessage.end_date >= today_d),
        )
        .order_by(InformativeMessage.id.desc())
        .all()
    )
    data = [
        {
            "id": m.id,
            "title": m.title,
            "content": m.content,
            "type": m.type,
            "active": m.active,
            "start_date": m.start_date.isoformat() if m.start_date else None,
            "end_date": m.end_date.isoformat() if m.end_date else None,
        }
        for m in rows
    ]
    cache.set_(cache_key, data, CACHE_TTL_SETTINGS)
    return data


# -----------------------------------------------------------------------------
# Categorias y productos
# -----------------------------------------------------------------------------


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    cached = cache.get("catalog:categories")
    if cached is not None:
        return cached
    rows = (
        db.query(Category)
        .filter(Category.active.is_(True), Category.archived.is_(False))
        .order_by(Category.name.asc())
        .all()
    )
    data = [serialize_category(c) for c in rows]
    cache.set_("catalog:categories", data, CACHE_TTL_CATEGORIES)
    return data


@router.get("/products")
def list_products(
    q: str | None = Query(default=None, max_length=120),
    category_id: int | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    order: str = Query(default="recent", pattern="^(recent|name|price_asc|price_desc)$"),
    db: Session = Depends(get_db),
):
    """Listado de productos publicados. Cache TTL 60s con clave por parametros.

    Enriquece cada producto con `stock` (agregado desde Inventory). Si Inventory
    no responde se sirve igual el listado pero con `inventory_available=False`
    para que el frontend no pinte "AGOTADO" sin informacion confiable.
    """
    cache_key = (
        f"catalog:products:q={q or ''}:cat={category_id or 0}"
        f":min={min_price or 0}:max={max_price or 0}:order={order}"
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    qry = (
        db.query(Product)
        .options(joinedload(Product.category), joinedload(Product.rating))
        .join(Category)
        .filter(
            Product.published.is_(True),
            Product.archived.is_(False),
            Category.active.is_(True),
            Category.archived.is_(False),
        )
    )
    if q:
        pattern = f"%{q.strip().lower()}%"
        qry = qry.filter(or_(Product.name.ilike(pattern), Product.description.ilike(pattern)))
    if category_id:
        qry = qry.filter(Product.category_id == category_id)
    if min_price is not None:
        qry = qry.filter(Product.base_price >= min_price)
    if max_price is not None:
        qry = qry.filter(Product.base_price <= max_price)
    if order == "name":
        qry = qry.order_by(Product.name.asc())
    elif order == "price_asc":
        qry = qry.order_by(Product.base_price.asc())
    elif order == "price_desc":
        qry = qry.order_by(Product.base_price.desc())
    else:
        qry = qry.order_by(Product.created_at.desc())

    # Stock real agregado desde Inventory (Cache-Aside con TTL corto).
    stock_map, inv_ok = get_stock_summary()
    data = [
        serialize_product_summary(p, stock_map.get(str(p.id)), inventory_available=inv_ok)
        for p in qry.all()
    ]
    cache.set_(cache_key, data, CACHE_TTL_PRODUCTS_LIST)
    return data


@router.get("/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    """Detalle de producto. Llama a Inventory para enriquecer con variantes."""
    p = (
        db.query(Product)
        .options(joinedload(Product.category), joinedload(Product.images), joinedload(Product.rating))
        .filter(Product.id == product_id)
        .first()
    )
    if not p or p.archived or not p.published:
        raise HTTPException(404, "Producto no encontrado.")
    if p.category and (p.category.archived or not p.category.active):
        raise HTTPException(404, "Producto no disponible.")

    variants, inv_ok = get_variants_for_product(product_id)
    return serialize_product_detail(p, variants=variants, inventory_available=inv_ok)


@router.get("/catalog")
def catalog_overview(db: Session = Depends(get_db)):
    """Resumen optimizado para la home: settings + mensajes + categorias + 6 productos destacados."""
    cached = cache.get("catalog:overview")
    if cached is not None:
        return cached
    s_data = store_settings(db)
    m_data = store_messages(db)
    cat_data = list_categories(db)
    products = (
        db.query(Product)
        .options(joinedload(Product.category), joinedload(Product.rating))
        .join(Category)
        .filter(
            Product.published.is_(True),
            Product.archived.is_(False),
            Category.active.is_(True),
            Category.archived.is_(False),
        )
        .order_by(Product.created_at.desc())
        .limit(6)
        .all()
    )
    stock_map, inv_ok = get_stock_summary()
    data = {
        "settings": s_data,
        "messages": m_data,
        "categories": cat_data,
        "featured_products": [
            serialize_product_summary(p, stock_map.get(str(p.id)), inventory_available=inv_ok)
            for p in products
        ],
    }
    cache.set_("catalog:overview", data, CACHE_TTL_PRODUCTS_LIST)
    return data
