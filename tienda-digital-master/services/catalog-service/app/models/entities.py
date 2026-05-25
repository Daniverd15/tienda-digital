"""Bounded context Catalog.

Solo entidades comerciales: productos, categorias, imagenes, configuracion
de tienda, mensajes informativos y resumen de rating (cache local actualizado
por el evento ReviewCreated de Commerce - en Nivel 3 via AMQP, ahora via
endpoint admin).

Las variantes (SKU, stock, reservas) pertenecen al Inventory Service. Catalog
las consulta por REST cuando hace falta enriquecer el detalle de un producto.
"""
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class TimestampMixin:
    """Campos created_at/updated_at compartidos por entidades editables."""
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class Category(Base, TimestampMixin):
    """Agrupador comercial de productos visible en navegacion."""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    archived = Column(Boolean, nullable=False, default=False)

    products = relationship("Product", back_populates="category")


class Product(Base, TimestampMixin):
    """Producto base del catalogo; las variantes viven en Inventory."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    name = Column(String(160), nullable=False)
    description = Column(Text, nullable=False)
    long_description = Column(Text, nullable=True)
    base_price = Column(Numeric(12, 2), nullable=False)
    published = Column(Boolean, nullable=False, default=True)
    archived = Column(Boolean, nullable=False, default=False)
    image_url = Column(String(500), nullable=True)

    category = relationship("Category", back_populates="products")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    rating = relationship("RatingSummary", uselist=False, back_populates="product",
                          cascade="all, delete-orphan")


class ProductImage(Base):
    """Imagen adicional asociada a la galeria de un producto."""
    __tablename__ = "product_images"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    image_url = Column(String(500), nullable=False)
    alt_text = Column(String(180), nullable=True)

    product = relationship("Product", back_populates="images")


class RatingSummary(Base):
    """Cache local de rating por producto, actualizada por Reviews vía endpoint admin."""

    __tablename__ = "rating_summaries"

    product_id = Column(Integer, ForeignKey("products.id"), primary_key=True)
    average = Column(Float, nullable=False, default=0.0)
    count = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    product = relationship("Product", back_populates="rating")


class StoreSetting(Base, TimestampMixin):
    """Configuracion de marca, contacto, moneda y umbral de stock."""
    __tablename__ = "store_settings"

    id = Column(Integer, primary_key=True)
    commercial_name = Column(String(120), nullable=False)
    logo_url = Column(String(500), nullable=True)
    primary_color = Column(String(20), nullable=False, default="#1f7a5c")
    secondary_color = Column(String(20), nullable=False, default="#f4b942")
    banner_url = Column(String(500), nullable=True)
    contact_email = Column(String(180), nullable=False)
    contact_phone = Column(String(40), nullable=False)
    currency = Column(String(10), nullable=False, default="COP")
    stock_threshold = Column(Integer, nullable=False, default=5)


class InformativeMessage(Base):
    """Mensaje publico con estado y ventana opcional de vigencia."""
    __tablename__ = "informative_messages"

    id = Column(Integer, primary_key=True)
    title = Column(String(160), nullable=False)
    content = Column(Text, nullable=False)
    type = Column(String(30), nullable=False, default="info")
    active = Column(Boolean, nullable=False, default=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
