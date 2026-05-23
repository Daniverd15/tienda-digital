"""Endpoints administrativos del Catalog Service.

Cada operacion de escritura invalida los prefijos de cache afectados, para
mantener la consistencia eventual del Cache-Aside.
"""
from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core import cache
from app.core.database import get_db
from app.core.deps import get_current_user_claims, require_admin
from app.models import (
    Category,
    InformativeMessage,
    Product,
    ProductImage,
    RatingSummary,
    StoreSetting,
)
from app.schemas import (
    ApiMessage,
    CategoryAdminUpsert,
    CategoryPublic,
    InformativeMessageAdminUpsert,
    InformativeMessagePublic,
    ProductAdminCreate,
    ProductAdminUpdate,
    ProductImagePublic,
    ProductImageUpsert,
    RatingSummaryUpsert,
    StoreSettingPublic,
    StoreSettingUpdate,
)
from app.services.serializers import (
    serialize_category,
    serialize_product_detail,
    serialize_product_summary,
)


router = APIRouter(prefix="/admin", tags=["Administracion catalogo"])

UPLOAD_DIR = Path("/app/uploads")
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _invalidate_catalog_cache() -> None:
    """Invalida lecturas cacheadas despues de una mutacion administrativa."""
    cache.invalidate_prefix("catalog:")


@router.post("/upload-image")
async def admin_upload_image(
    file: UploadFile = File(...),
    _: dict = Depends(require_admin),
):
    """Valida, limita y guarda imagenes subidas para productos."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(422, "Formato no soportado. Usa JPG, PNG o WebP.")

    content = await file.read(MAX_IMAGE_BYTES + 1)
    await file.close()
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "La imagen supera el maximo permitido de 5 MB.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{ALLOWED_IMAGE_TYPES[file.content_type]}"
    path = UPLOAD_DIR / filename
    path.write_bytes(content)
    return {"url": f"/uploads/{filename}"}


# -----------------------------------------------------------------------------
# Categorias
# -----------------------------------------------------------------------------


@router.get("/categories", response_model=list[CategoryPublic])
def admin_list_categories(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Lista categorias para administracion."""
    return db.query(Category).order_by(Category.name.asc()).all()


@router.post("/categories", response_model=CategoryPublic, status_code=status.HTTP_201_CREATED)
def admin_create_category(
    payload: CategoryAdminUpsert,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Crea una categoria unica e invalida cache publico."""
    if db.query(Category).filter(Category.name == payload.name).first():
        raise HTTPException(409, "Ya existe una categoria con ese nombre.")
    c = Category(**payload.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    _invalidate_catalog_cache()
    return c


@router.put("/categories/{category_id}", response_model=CategoryPublic)
def admin_update_category(
    category_id: int,
    payload: CategoryAdminUpsert,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Actualiza una categoria existente e invalida cache publico."""
    c = db.query(Category).filter(Category.id == category_id).first()
    if not c:
        raise HTTPException(404, "Categoria no encontrada.")
    for f, v in payload.model_dump().items():
        setattr(c, f, v)
    db.commit()
    db.refresh(c)
    _invalidate_catalog_cache()
    return c


@router.delete("/categories/{category_id}", response_model=ApiMessage)
def admin_archive_category(
    category_id: int,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Archivado logico (soft delete)."""
    c = db.query(Category).filter(Category.id == category_id).first()
    if not c:
        raise HTTPException(404, "Categoria no encontrada.")
    c.archived = True
    c.active = False
    db.commit()
    _invalidate_catalog_cache()
    return ApiMessage(message="Categoria archivada.")


# -----------------------------------------------------------------------------
# Productos
# -----------------------------------------------------------------------------


@router.get("/products")
def admin_list_products(
    q: str | None = None,
    include_archived: bool = False,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Lista productos con busqueda y opcion de incluir archivados."""
    qry = db.query(Product)
    if not include_archived:
        qry = qry.filter(Product.archived.is_(False))
    if q:
        pattern = f"%{q.strip().lower()}%"
        qry = qry.filter(or_(Product.name.ilike(pattern), Product.description.ilike(pattern)))
    return [serialize_product_summary(p) for p in qry.order_by(Product.created_at.desc()).all()]


@router.post("/products", status_code=status.HTTP_201_CREATED)
def admin_create_product(
    payload: ProductAdminCreate,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Crea un producto base y su resumen de rating inicial."""
    cat = db.query(Category).filter(Category.id == payload.category_id).first()
    if not cat:
        raise HTTPException(422, "category_id invalido.")
    p = Product(**payload.model_dump())
    db.add(p)
    db.flush()
    db.add(RatingSummary(product_id=p.id, average=0.0, count=0))
    db.commit()
    db.refresh(p)
    _invalidate_catalog_cache()
    return serialize_product_detail(p, variants=[], inventory_available=False)


@router.put("/products/{product_id}")
def admin_update_product(
    product_id: int,
    payload: ProductAdminUpdate,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Actualiza campos comerciales de producto y valida categoria si cambia."""
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(404, "Producto no encontrado.")
    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data:
        cat = db.query(Category).filter(Category.id == data["category_id"]).first()
        if not cat:
            raise HTTPException(422, "category_id invalido.")
    for f, v in data.items():
        setattr(p, f, v)
    db.commit()
    db.refresh(p)
    _invalidate_catalog_cache()
    return serialize_product_summary(p)


@router.delete("/products/{product_id}", response_model=ApiMessage)
def admin_archive_product(
    product_id: int,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Archiva y despublica un producto sin borrar su historial."""
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(404, "Producto no encontrado.")
    p.archived = True
    p.published = False
    db.commit()
    _invalidate_catalog_cache()
    return ApiMessage(message="Producto archivado.")


# Galeria
@router.get("/products/{product_id}/images", response_model=list[ProductImagePublic])
def admin_list_images(
    product_id: int,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Lista imagenes de galeria asociadas a un producto."""
    return db.query(ProductImage).filter(ProductImage.product_id == product_id).all()


@router.post("/products/{product_id}/images", response_model=ProductImagePublic,
             status_code=status.HTTP_201_CREATED)
def admin_add_image(
    product_id: int,
    payload: ProductImageUpsert,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Agrega una imagen a la galeria del producto e invalida cache."""
    if not db.query(Product).filter(Product.id == product_id).first():
        raise HTTPException(404, "Producto no encontrado.")
    img = ProductImage(product_id=product_id, **payload.model_dump())
    db.add(img)
    db.commit()
    db.refresh(img)
    _invalidate_catalog_cache()
    return img


@router.delete("/products/{product_id}/images/{image_id}", response_model=ApiMessage)
def admin_delete_image(
    product_id: int,
    image_id: int,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Elimina una imagen de galeria y refresca cache publico."""
    img = (
        db.query(ProductImage)
        .filter(ProductImage.id == image_id, ProductImage.product_id == product_id)
        .first()
    )
    if not img:
        raise HTTPException(404, "Imagen no encontrada.")
    db.delete(img)
    db.commit()
    _invalidate_catalog_cache()
    return ApiMessage(message="Imagen eliminada.")


# -----------------------------------------------------------------------------
# Rating summary (sera invocado por Reviews/Commerce cuando se publique una review)
# -----------------------------------------------------------------------------


@router.put("/products/{product_id}/rating", response_model=ApiMessage)
def admin_update_rating(
    product_id: int,
    payload: RatingSummaryUpsert,
    _: dict = Depends(get_current_user_claims),  # Commerce lo llama con el JWT del usuario que reseno
    db: Session = Depends(get_db),
):
    """Actualiza el resumen de rating calculado por Commerce."""
    if payload.product_id != product_id:
        raise HTTPException(422, "product_id en path y body no coinciden.")
    if not db.query(Product).filter(Product.id == product_id).first():
        raise HTTPException(404, "Producto no encontrado.")
    summary = db.query(RatingSummary).filter(RatingSummary.product_id == product_id).first()
    if not summary:
        summary = RatingSummary(product_id=product_id, average=payload.average, count=payload.count)
        db.add(summary)
    else:
        summary.average = payload.average
        summary.count = payload.count
    db.commit()
    _invalidate_catalog_cache()
    return ApiMessage(message="Rating actualizado.")


# -----------------------------------------------------------------------------
# Store settings
# -----------------------------------------------------------------------------


@router.get("/store/settings", response_model=StoreSettingPublic)
def admin_get_settings(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Obtiene configuracion de tienda para el panel admin."""
    s = db.query(StoreSetting).order_by(StoreSetting.id.asc()).first()
    if not s:
        raise HTTPException(404, "Configuracion no inicializada.")
    return s


@router.put("/store/settings", response_model=StoreSettingPublic)
def admin_update_settings(
    payload: StoreSettingUpdate,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Actualiza branding/contacto de tienda e invalida cache publico."""
    s = db.query(StoreSetting).order_by(StoreSetting.id.asc()).first()
    if not s:
        raise HTTPException(404, "Configuracion no inicializada.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(s, f, v)
    db.commit()
    db.refresh(s)
    _invalidate_catalog_cache()
    return s


# -----------------------------------------------------------------------------
# Mensajes informativos
# -----------------------------------------------------------------------------


@router.get("/messages", response_model=list[InformativeMessagePublic])
def admin_list_messages(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Lista mensajes informativos administrables."""
    return db.query(InformativeMessage).order_by(InformativeMessage.id.desc()).all()


@router.post("/messages", response_model=InformativeMessagePublic,
             status_code=status.HTTP_201_CREATED)
def admin_create_message(
    payload: InformativeMessageAdminUpsert,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Crea un mensaje informativo y refresca cache publico."""
    m = InformativeMessage(**payload.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    _invalidate_catalog_cache()
    return m


@router.put("/messages/{message_id}", response_model=InformativeMessagePublic)
def admin_update_message(
    message_id: int,
    payload: InformativeMessageAdminUpsert,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Actualiza un mensaje informativo y refresca cache publico."""
    m = db.query(InformativeMessage).filter(InformativeMessage.id == message_id).first()
    if not m:
        raise HTTPException(404, "Mensaje no encontrado.")
    for f, v in payload.model_dump().items():
        setattr(m, f, v)
    db.commit()
    db.refresh(m)
    _invalidate_catalog_cache()
    return m


@router.delete("/messages/{message_id}", response_model=ApiMessage)
def admin_delete_message(
    message_id: int,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Elimina un mensaje informativo e invalida cache publico."""
    m = db.query(InformativeMessage).filter(InformativeMessage.id == message_id).first()
    if not m:
        raise HTTPException(404, "Mensaje no encontrado.")
    db.delete(m)
    db.commit()
    _invalidate_catalog_cache()
    return ApiMessage(message="Mensaje eliminado.")
