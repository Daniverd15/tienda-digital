"""Bounded context Inventory.

Fuente unica de verdad del stock. Variantes (SKU) y movimientos.
Las reservas tienen `expires_at` y un scheduler las libera al vencer.

product_id es una referencia LOGICA a Catalog (NO foreign key cross-DB).
order_id en reservas es una referencia LOGICA a Commerce.
"""
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class TimestampMixin:
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class ProductVariant(Base, TimestampMixin):
    """SKU con stock, costo y precio. La fuente de verdad del inventario.

    Restricciones:
    - SKU unico (global).
    - (product_id, color, size) unico para evitar duplicados visibles al
      cliente. NULL en color o size se permite (un producto sin variantes de
      color, p.ej. una mochila, tendra solo una fila con color y size NULL).
    """

    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("sku", name="uq_variant_sku"),
        UniqueConstraint("product_id", "color", "size", name="uq_variant_combo"),
    )

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, nullable=False, index=True)  # ref logica a Catalog
    sku = Column(String(80), nullable=False)
    color = Column(String(80), nullable=True)        # nombre del color (ej. "Negro")
    color_hex = Column(String(9), nullable=True)     # valor visual (#000000, #ff5733aa)
    size = Column(String(80), nullable=True)
    custom_attribute = Column(String(160), nullable=True)
    cost = Column(Numeric(12, 2), nullable=False, default=0)
    price = Column(Numeric(12, 2), nullable=False, default=0)
    stock = Column(Integer, nullable=False, default=0)            # cantidad fisica total
    reserved_stock = Column(Integer, nullable=False, default=0)   # bloqueado por reservas activas
    active = Column(Boolean, nullable=False, default=True)

    reservations = relationship("StockReservation", back_populates="variant",
                                cascade="all, delete-orphan")
    movements = relationship("StockMovement", back_populates="variant",
                             cascade="all, delete-orphan")

    @property
    def available(self) -> int:
        return max(0, self.stock - self.reserved_stock)


class StockReservation(Base):
    """Reserva temporal de stock para un order_id durante el checkout.

    Estados: PENDING -> CONFIRMED (al recibir PaymentApproved)
                     -> RELEASED  (compensacion)
                     -> EXPIRED   (scheduler tras expires_at)
    """

    __tablename__ = "stock_reservations"
    __table_args__ = (
        Index("ix_reservation_order", "order_id"),
        Index("ix_reservation_status_expires", "status", "expires_at"),
    )

    id = Column(Integer, primary_key=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=False, index=True)
    order_id = Column(String(60), nullable=False)  # ref logica a Commerce (order_code o id)
    quantity = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    variant = relationship("ProductVariant", back_populates="reservations")


class StockMovement(Base):
    """Auditoria de cambios de stock: entrada, salida, ajuste, reserva, confirmacion."""

    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=False, index=True)
    movement_type = Column(String(30), nullable=False)
    # entry, exit, adjust, reserve, confirm, release, expire
    quantity = Column(Integer, nullable=False)
    reason = Column(String(250), nullable=False)
    user_id = Column(Integer, nullable=True)            # ref logica a Auth
    order_id = Column(String(60), nullable=True)        # ref logica a Commerce si aplica
    correlation_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    variant = relationship("ProductVariant", back_populates="movements")


class LowStockAlert(Base):
    """Alerta generada cuando una variante cruza el umbral minimo."""

    __tablename__ = "low_stock_alerts"

    id = Column(Integer, primary_key=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=False, index=True)
    threshold = Column(Integer, nullable=False)
    stock_at_alert = Column(Integer, nullable=False)
    resolved = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    variant = relationship("ProductVariant")
