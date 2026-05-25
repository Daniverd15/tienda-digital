"""Pydantic schemas del Catalog Service."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# -----------------------------------------------------------------------------
# Categorias
# -----------------------------------------------------------------------------


class CategoryPublic(BaseModel):
    """Categoria expuesta al frontend publico o administrativo."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    active: bool
    archived: bool


class CategoryAdminUpsert(BaseModel):
    """Entrada administrativa para crear o actualizar categorias."""
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    active: bool = True
    archived: bool = False


# -----------------------------------------------------------------------------
# Productos
# -----------------------------------------------------------------------------


class ProductImagePublic(BaseModel):
    """Imagen de galeria serializada hacia el frontend."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_url: str
    alt_text: str | None


class ProductImageUpsert(BaseModel):
    """Entrada administrativa para agregar o editar imagenes."""
    image_url: str = Field(min_length=4, max_length=500)
    alt_text: str | None = None


class ProductSummary(BaseModel):
    """Vista corta usada en listados."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    name: str
    description: str
    base_price: float
    image_url: str | None
    published: bool
    archived: bool
    average_rating: float = 0.0
    reviews_count: int = 0


class ProductPublic(BaseModel):
    """Vista completa usada en detalle. Las variantes vienen de Inventory por REST."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    category_name: str | None
    name: str
    description: str
    long_description: str | None
    base_price: float
    image_url: str | None
    published: bool
    archived: bool
    gallery: list[ProductImagePublic]
    average_rating: float
    reviews_count: int
    variants: list[dict] = []           # enriquecido desde Inventory cuando aplica
    inventory_available: bool = True    # False si Inventory esta caido


class ProductAdminCreate(BaseModel):
    """Entrada para crear un producto base en Catalog Service."""
    category_id: int
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=2)
    long_description: str | None = None
    base_price: float = Field(ge=0)
    published: bool = True
    archived: bool = False
    image_url: str | None = None


class ProductAdminUpdate(BaseModel):
    """Entrada parcial para actualizar campos comerciales del producto."""
    category_id: int | None = None
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = None
    long_description: str | None = None
    base_price: float | None = Field(default=None, ge=0)
    published: bool | None = None
    archived: bool | None = None
    image_url: str | None = None


# -----------------------------------------------------------------------------
# Rating summary (actualizado por Reviews cuando se aprueba/cambia una resena)
# -----------------------------------------------------------------------------


class RatingSummaryUpsert(BaseModel):
    """Resumen de rating enviado por Commerce cuando cambian resenas."""
    product_id: int
    average: float = Field(ge=0, le=5)
    count: int = Field(ge=0)


# -----------------------------------------------------------------------------
# Store settings
# -----------------------------------------------------------------------------


class StoreSettingPublic(BaseModel):
    """Configuracion de tienda expuesta al frontend."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    commercial_name: str
    logo_url: str | None
    primary_color: str
    secondary_color: str
    banner_url: str | None
    contact_email: EmailStr
    contact_phone: str
    currency: str
    stock_threshold: int


class StoreSettingUpdate(BaseModel):
    """Actualizacion parcial de branding y parametros comerciales."""
    commercial_name: str | None = Field(default=None, min_length=2, max_length=120)
    logo_url: str | None = None
    primary_color: str | None = Field(default=None, max_length=20)
    secondary_color: str | None = Field(default=None, max_length=20)
    banner_url: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=40)
    currency: str | None = Field(default=None, max_length=10)
    stock_threshold: int | None = Field(default=None, ge=0)


# -----------------------------------------------------------------------------
# Mensajes informativos
# -----------------------------------------------------------------------------


class InformativeMessagePublic(BaseModel):
    """Mensaje informativo visible segun estado y fechas."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    type: str
    active: bool
    start_date: date | None
    end_date: date | None


class InformativeMessageAdminUpsert(BaseModel):
    """Entrada administrativa para mensajes informativos."""
    title: str = Field(min_length=2, max_length=160)
    content: str
    type: str = Field(default="info", max_length=30)
    active: bool = True
    start_date: date | None = None
    end_date: date | None = None


class ApiMessage(BaseModel):
    """Respuesta generica de confirmacion."""
    message: str
