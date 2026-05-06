from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
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


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(180), unique=True, index=True, nullable=False)
    phone = Column(String(40), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False, default="customer")
    active = Column(Boolean, nullable=False, default=True)

    carts = relationship("Cart", back_populates="user")
    orders = relationship("Order", back_populates="user")


class StoreSetting(Base, TimestampMixin):
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
    __tablename__ = "informative_messages"

    id = Column(Integer, primary_key=True)
    title = Column(String(160), nullable=False)
    content = Column(Text, nullable=False)
    type = Column(String(30), nullable=False, default="info")
    active = Column(Boolean, nullable=False, default=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    archived = Column(Boolean, nullable=False, default=False)

    products = relationship("Product", back_populates="category")


class Product(Base, TimestampMixin):
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
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="product")


class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    image_url = Column(String(500), nullable=False)
    alt_text = Column(String(180), nullable=True)

    product = relationship("Product", back_populates="images")


class ProductVariant(Base, TimestampMixin):
    __tablename__ = "product_variants"
    __table_args__ = (UniqueConstraint("sku", name="uq_product_variant_sku"),)

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    sku = Column(String(80), nullable=False)
    color = Column(String(80), nullable=True)
    size = Column(String(80), nullable=True)
    custom_attribute = Column(String(160), nullable=True)
    cost = Column(Numeric(12, 2), nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    reserved_stock = Column(Integer, nullable=False, default=0)
    active = Column(Boolean, nullable=False, default=True)

    product = relationship("Product", back_populates="variants")


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id = Column(Integer, primary_key=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=False)
    movement_type = Column(String(30), nullable=False)
    quantity = Column(Integer, nullable=False)
    reason = Column(String(250), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    variant = relationship("ProductVariant")
    user = relationship("User")


class Cart(Base, TimestampMixin):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(30), nullable=False, default="open")

    user = relationship("User", back_populates="carts")
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "variant_id", name="uq_cart_variant"),)

    id = Column(Integer, primary_key=True)
    cart_id = Column(Integer, ForeignKey("carts.id"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)

    cart = relationship("Cart", back_populates="items")
    variant = relationship("ProductVariant")


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    order_code = Column(String(40), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(40), nullable=False)
    payment_status = Column(String(40), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)
    additional_costs = Column(Numeric(12, 2), nullable=False, default=0)
    discount = Column(Numeric(12, 2), nullable=False, default=0)
    total = Column(Numeric(12, 2), nullable=False)
    delivery_name = Column(String(160), nullable=False)
    delivery_address = Column(String(250), nullable=False)
    delivery_city = Column(String(120), nullable=False)
    billing_document = Column(String(80), nullable=False)
    contact_phone = Column(String(40), nullable=False)
    contact_email = Column(String(180), nullable=False)

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=False)
    product_name = Column(String(160), nullable=False)
    variant_description = Column(String(250), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    total = Column(Numeric(12, 2), nullable=False)

    order = relationship("Order", back_populates="items")
    variant = relationship("ProductVariant")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    provider = Column(String(80), nullable=False)
    transaction_reference = Column(String(120), nullable=False)
    status = Column(String(40), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    response_message = Column(String(250), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    order = relationship("Order", back_populates="payments")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    title = Column(String(160), nullable=False)
    message = Column(Text, nullable=False)
    read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User")
    order = relationship("Order")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("user_id", "product_id", "order_id", name="uq_review_order_product"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    approved = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User")
    product = relationship("Product", back_populates="reviews")
    order = relationship("Order")


class Employee(Base, TimestampMixin):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True)
    name = Column(String(160), nullable=False)
    document = Column(String(80), unique=True, nullable=False)
    position = Column(String(120), nullable=False)
    salary = Column(Numeric(12, 2), nullable=False)
    employment_status = Column(String(40), nullable=False, default="active")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True)
    expense_type = Column(String(80), nullable=False)
    description = Column(String(250), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    observation = Column(Text, nullable=True)
    expense_date = Column(Date, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    creator = relationship("User")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(120), nullable=False)
    entity = Column(String(120), nullable=False)
    entity_id = Column(String(80), nullable=True)
    previous_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User")


class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True)
    level = Column(String(30), nullable=False)
    message = Column(Text, nullable=False)
    context = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

