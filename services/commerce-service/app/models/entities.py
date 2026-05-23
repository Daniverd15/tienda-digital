"""Bounded context Commerce.

Agrupa carrito, checkout, pedidos, estados logisticos, resenas y notificaciones.
En el MVP tambien incluye empleados, gastos y bitacora administrativa de pedidos
(que en evolucion futura saldrian a Finance y Audit services).

Todas las referencias cross-context (user_id, variant_id, product_id) son
identificadores logicos, NO foreign keys (no podemos JOIN entre BDs distintas).
"""
from sqlalchemy import (
    Boolean,
    Column,
    Date,
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
    """Campos temporales comunes para entidades modificables."""
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


# -----------------------------------------------------------------------------
# Carrito
# -----------------------------------------------------------------------------


class Cart(Base, TimestampMixin):
    """Carrito abierto/checkout del usuario dentro de Commerce."""
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)  # ref logica a Auth
    status = Column(String(30), nullable=False, default="open")  # open, checked_out, abandoned

    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    """Linea de carrito con snapshot de producto y variante."""
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "variant_id", name="uq_cart_variant"),)

    id = Column(Integer, primary_key=True)
    cart_id = Column(Integer, ForeignKey("carts.id"), nullable=False)
    variant_id = Column(Integer, nullable=False)         # ref logica a Inventory
    product_id = Column(Integer, nullable=False)          # ref logica a Catalog
    product_name = Column(String(160), nullable=False)    # snapshot
    variant_description = Column(String(250), nullable=False)  # snapshot
    image_url = Column(String(500), nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)

    cart = relationship("Cart", back_populates="items")


# -----------------------------------------------------------------------------
# Pedidos
# -----------------------------------------------------------------------------


class Order(Base, TimestampMixin):
    """Pedido real creado solo cuando la SAGA termina en PAID."""
    __tablename__ = "orders"
    __table_args__ = (Index("ix_order_user_status", "user_id", "status"),)

    id = Column(Integer, primary_key=True)
    order_code = Column(String(40), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    status = Column(String(40), nullable=False, default="CREATED")
    # CREATED, AWAITING_PAYMENT, PAID, PAGO_PENDIENTE, PAGO_RECHAZADO, SIN_STOCK,
    # EN_PREPARACION, ENVIADO, ENTREGADO, CANCELADA, EXPIRADA
    payment_status = Column(String(40), nullable=False, default="PENDING")
    payment_id = Column(Integer, nullable=True)
    payment_reference = Column(String(120), nullable=True)
    payment_message = Column(String(250), nullable=True)
    subtotal = Column(Numeric(12, 2), nullable=False)
    additional_costs = Column(Numeric(12, 2), nullable=False, default=0)
    discount = Column(Numeric(12, 2), nullable=False, default=0)
    total = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="COP")
    delivery_name = Column(String(160), nullable=False)
    delivery_address = Column(String(250), nullable=False)
    delivery_city = Column(String(120), nullable=False)
    billing_document = Column(String(80), nullable=False)
    contact_phone = Column(String(40), nullable=False)
    contact_email = Column(String(180), nullable=False)
    correlation_id = Column(String(64), nullable=True)

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    history = relationship("OrderStatusHistory", back_populates="order",
                           cascade="all, delete-orphan")
    audit = relationship("OrderAuditLog", back_populates="order",
                         cascade="all, delete-orphan")


class OrderItem(Base):
    """Snapshot historico de producto, precio y costo dentro del pedido."""
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    variant_id = Column(Integer, nullable=False)        # ref logica
    product_id = Column(Integer, nullable=False)         # ref logica
    product_name = Column(String(160), nullable=False)   # snapshot
    variant_description = Column(String(250), nullable=False)
    image_url = Column(String(500), nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    unit_cost = Column(Numeric(12, 2), nullable=False, default=0)   # snapshot del costo en Inventory al momento del checkout
    total = Column(Numeric(12, 2), nullable=False)

    order = relationship("Order", back_populates="items")


class OrderStatusHistory(Base):
    """Timeline visible de transiciones logisticas del pedido."""
    __tablename__ = "order_status_history"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    from_status = Column(String(40), nullable=True)
    to_status = Column(String(40), nullable=False)
    changed_by = Column(Integer, nullable=True)  # ref logica
    notes = Column(String(250), nullable=True)
    changed_at = Column(DateTime, server_default=func.now(), nullable=False)

    order = relationship("Order", back_populates="history")


class OrderAuditLog(Base):
    """Bitacora administrativa de acciones sobre pedidos (RNF-14)."""

    __tablename__ = "order_audit_logs"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    action = Column(String(80), nullable=False)
    performed_by = Column(Integer, nullable=True)  # ref logica
    details = Column(Text, nullable=True)
    correlation_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    order = relationship("Order", back_populates="audit")


class FailedCheckoutAttempt(Base):
    """Intento de checkout que NO termino en PAID.

    En la version anterior estos casos se persistian como Order con estados
    artificiales (PAGO_RECHAZADO, SIN_STOCK, PAGO_PENDIENTE). Como esos
    estados no representan pedidos reales y contaminaban el panel admin y las
    metricas financieras, ahora se guardan separados aqui solo para
    trazabilidad y soporte (saber por que un cliente no pudo comprar).
    """
    __tablename__ = "failed_checkout_attempts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    attempt_code = Column(String(40), nullable=False, index=True)
    reason_code = Column(String(60), nullable=False)
    # out_of_stock | payment_rejected | payment_unavailable |
    # inventory_unavailable | inventory_error | payment_pending | payment_failed
    message = Column(String(500), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False, default=0)
    correlation_id = Column(String(64), nullable=True)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


# -----------------------------------------------------------------------------
# Reseñas
# -----------------------------------------------------------------------------


class Review(Base):
    """Resena de un producto.

    Regla del SRS: solo se permite resenar productos comprados y entregados.
    Validacion: existe un OrderItem para (user_id, product_id) en una orden
    con status ENTREGADO; y no debe existir ya un Review (user, product, order).
    """

    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", "order_id", name="uq_review_user_product_order"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    product_id = Column(Integer, nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1..5
    comment = Column(Text, nullable=True)
    approved = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


# -----------------------------------------------------------------------------
# Notificaciones (inbox del usuario)
# -----------------------------------------------------------------------------


class Notification(Base):
    """Notificacion in-app para eventos de compra y pedidos."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    title = Column(String(160), nullable=False)
    message = Column(Text, nullable=False)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


# -----------------------------------------------------------------------------
# Empleados y gastos (MVP los mantiene en Commerce; saldran a Finance Service)
# -----------------------------------------------------------------------------


class Employee(Base, TimestampMixin):
    """Empleado usado para calculos de nomina en finanzas MVP."""
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True)
    name = Column(String(160), nullable=False)
    document = Column(String(80), unique=True, nullable=False)
    position = Column(String(120), nullable=False)
    salary = Column(Numeric(12, 2), nullable=False, default=0)
    employment_status = Column(String(40), nullable=False, default="active")


class Expense(Base):
    """Gasto operativo usado para calcular utilidad neta."""
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True)
    expense_type = Column(String(80), nullable=False)
    description = Column(String(250), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    observation = Column(Text, nullable=True)
    expense_date = Column(Date, nullable=False)
    created_by = Column(Integer, nullable=True)  # ref logica al admin
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
