"""Entidades SQLAlchemy del bounded context Inventory.

================================================================================
PROPOSITO
================================================================================
Modela el dominio de stock fisico de la tienda. Es la FUENTE UNICA DE VERDAD
del inventario: ningun otro microservicio tiene autoridad sobre el stock.

================================================================================
ENTIDADES
================================================================================
- ProductVariant   : SKU con stock fisico, costo, precio. Una variante por
                     combinacion (producto, color, talla).
- StockReservation : reserva temporal durante checkout. Se libera al cobrar
                     (CONFIRMED), al fallar el cobro (RELEASED) o al expirar
                     el TTL sin resolverse (EXPIRED, por el scheduler).
- StockMovement    : bitacora de TODOS los cambios de stock con motivo +
                     usuario + correlation_id para auditoria.
- LowStockAlert    : alerta visible al admin cuando una variante baja del
                     umbral minimo configurado.

================================================================================
REFERENCIAS LOGICAS (no foreign keys cross-DB)
================================================================================
- product_id en ProductVariant apunta a Product de Catalog (otro servicio,
  otra DB). NO es foreign key fisica: se valida con una llamada HTTP a
  Catalog al crear la variante.
- order_id en StockReservation y StockMovement apunta al order_code de
  Order en Commerce (otro servicio, otra DB). Es String porque Commerce
  usa codigos legibles tipo "ORD-20260520-XXXXXXXX".
- user_id en StockMovement apunta a User de Auth. Tambien string para
  consistencia.

Esta arquitectura permite que cada microservicio escale y se despliegue
independientemente (Database per Service) sin acoplarse a nivel SQL.
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
    """Mixin que agrega columnas created_at y updated_at a cualquier entidad.

    server_default=func.now() hace que MySQL ponga la fecha automaticamente.
    onupdate=func.now() en updated_at hace que SQLAlchemy actualice el
    timestamp cada vez que la fila se modifica.
    """
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class ProductVariant(Base, TimestampMixin):
    """SKU con stock fisico, costo y precio. Fuente de verdad del inventario.

    Restricciones SQL:
      - uq_variant_sku: SKU unico globalmente (no se repite entre productos).
      - uq_variant_combo: (product_id, color, size) unico para evitar
        duplicados visibles al cliente. NULL en color o size se permite
        (un producto sin variantes de color, ej. una mochila, tendra solo
        una fila con color y size NULL).

    Campos especiales:
      - color: nombre legible ("Negro", "Blanco")
      - color_hex: hex visual ("#000000") usado por el frontend para mostrar
        bolitas de color al seleccionar variante.
      - stock: cantidad fisica TOTAL en inventario (no se modifica al reservar).
      - reserved_stock: cantidad BLOQUEADA por reservas PENDING (se incrementa
        al reservar y se decrementa al confirmar/liberar).
      - available (property): stock - reserved_stock. Lo que el cliente ve.
    """

    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("sku", name="uq_variant_sku"),
        UniqueConstraint("product_id", "color", "size", name="uq_variant_combo"),
    )

    id = Column(Integer, primary_key=True)
    # ref logica a Catalog: NO es foreign key fisica (database per service).
    # Se valida con HTTP call al crear la variante.
    product_id = Column(Integer, nullable=False, index=True)
    sku = Column(String(80), nullable=False)
    color = Column(String(80), nullable=True)        # nombre del color (ej. "Negro")
    color_hex = Column(String(9), nullable=True)     # valor visual (#000000, #ff5733aa)
    size = Column(String(80), nullable=True)
    custom_attribute = Column(String(160), nullable=True)
    cost = Column(Numeric(12, 2), nullable=False, default=0)         # costo de adquisicion
    price = Column(Numeric(12, 2), nullable=False, default=0)        # precio de venta
    stock = Column(Integer, nullable=False, default=0)               # cantidad fisica total
    reserved_stock = Column(Integer, nullable=False, default=0)      # bloqueado por reservas activas
    active = Column(Boolean, nullable=False, default=True)

    # Relaciones internas (mismo schema MySQL → FK fisica permitida).
    # cascade=delete-orphan: si se borra una variante, sus reservas y
    # movimientos asociados se borran tambien.
    reservations = relationship("StockReservation", back_populates="variant",
                                cascade="all, delete-orphan")
    movements = relationship("StockMovement", back_populates="variant",
                             cascade="all, delete-orphan")

    @property
    def available(self) -> int:
        """Cantidad disponible para vender = stock total - reservas activas.

        max(0, ...) defensivo: si por algun bug reserved_stock supera stock,
        no queremos devolver negativos. El cliente ve 0 (= AGOTADO).
        """
        return max(0, self.stock - self.reserved_stock)


class StockReservation(Base):
    """Reserva temporal de stock para un order_id durante el checkout.

    Maquina de estados:
      PENDING ─→ CONFIRMED (al recibir PaymentApproved → /confirm)
              └→ RELEASED  (compensacion → /release)
              └→ EXPIRED   (scheduler tras expires_at sin resolverse)

    Indices:
      - ix_reservation_order: lookup rapido por order_id (lo usa /confirm y /release).
      - ix_reservation_status_expires: lookup rapido del scheduler para
        encontrar reservas PENDING vencidas.
    """

    __tablename__ = "stock_reservations"
    __table_args__ = (
        Index("ix_reservation_order", "order_id"),
        Index("ix_reservation_status_expires", "status", "expires_at"),
    )

    id = Column(Integer, primary_key=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=False, index=True)
    # ref logica a Commerce: el order_code (string) en vez de un int.
    # Permite que Commerce identifique reservas sin compartir DB.
    order_id = Column(String(60), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    # Vence en (created_at + ttl_seconds del payload de /reserve, default 15 min).
    # El scheduler busca reservas con expires_at <= now() y las libera.
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    variant = relationship("ProductVariant", back_populates="reservations")


class StockMovement(Base):
    """Auditoria de TODOS los cambios de stock con motivo y responsable.

    Lo usa el admin para reconciliar discrepancias ("por que el stock bajo
    de 10 a 7?") y la bitacora de auditoria (RNF-03 trazabilidad).

    Tipos de movimiento (movement_type):
      - entry:   entrada de inventario (admin recibe pedido del proveedor)
      - exit:    salida manual del admin
      - adjust:  ajuste manual (puede ser + o -, ej. conteo fisico)
      - reserve: reserva temporal por checkout
      - confirm: confirmacion de venta (stock fisico baja)
      - release: liberacion por compensacion SAGA
      - expire:  liberacion automatica por timeout del scheduler
    """

    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=False, index=True)
    movement_type = Column(String(30), nullable=False)
    # entry, exit, adjust, reserve, confirm, release, expire
    quantity = Column(Integer, nullable=False)
    reason = Column(String(250), nullable=False)
    user_id = Column(Integer, nullable=True)            # ref logica a Auth
    order_id = Column(String(60), nullable=True)        # ref logica a Commerce si aplica
    # correlation_id propagado desde el gateway: permite cruzar este
    # movimiento con los eventos del checkout en commerce_db y access_logs.
    correlation_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    variant = relationship("ProductVariant", back_populates="movements")


class LowStockAlert(Base):
    """Alerta generada cuando una variante alcanza el umbral minimo configurado.

    Visible en el panel admin (Inventario > Alertas). Se crea automaticamente
    cuando el scheduler detecta que stock <= threshold. El admin puede
    marcarla como resolved=True cuando reabastece.
    """

    __tablename__ = "low_stock_alerts"

    id = Column(Integer, primary_key=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=False, index=True)
    threshold = Column(Integer, nullable=False)
    stock_at_alert = Column(Integer, nullable=False)
    resolved = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    variant = relationship("ProductVariant")
