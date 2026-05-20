"""Schemas Pydantic del Commerce Service."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# -----------------------------------------------------------------------------
# Carrito
# -----------------------------------------------------------------------------


class CartItemAdd(BaseModel):
    variant_id: int
    quantity: int = Field(ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1)


class CartItemPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    variant_id: int
    product_id: int
    product_name: str
    variant_description: str
    image_url: str | None
    sku: str | None = None
    quantity: int
    unit_price: float
    total: float
    available_stock: int | None = None
    has_enough_stock: bool = True


class CartPublic(BaseModel):
    id: int
    user_id: int
    status: str
    items: list[CartItemPublic]
    subtotal: float
    item_count: int


# -----------------------------------------------------------------------------
# Checkout y pedidos
# -----------------------------------------------------------------------------


class CheckoutRequest(BaseModel):
    delivery_name: str = Field(min_length=2, max_length=160)
    delivery_address: str = Field(min_length=4, max_length=250)
    delivery_city: str = Field(min_length=2, max_length=120)
    billing_document: str = Field(min_length=4, max_length=80)
    contact_phone: str = Field(min_length=6, max_length=40)
    contact_email: EmailStr
    card_token: str | None = Field(default=None, max_length=120)


class OrderItemPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    variant_id: int
    product_id: int
    product_name: str
    variant_description: str
    image_url: str | None
    quantity: int
    unit_price: float
    total: float


class OrderStatusEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_status: str | None
    to_status: str
    changed_by: int | None
    notes: str | None
    changed_at: datetime


class OrderPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_code: str
    user_id: int
    status: str
    payment_status: str
    payment_reference: str | None
    payment_message: str | None
    subtotal: float
    additional_costs: float
    discount: float
    total: float
    currency: str
    delivery_name: str
    delivery_address: str
    delivery_city: str
    billing_document: str
    contact_phone: str
    contact_email: EmailStr
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemPublic]
    history: list[OrderStatusEntry] = []


class OrderStatusUpdate(BaseModel):
    new_status: str = Field(pattern="^(EN_PREPARACION|ENVIADO|ENTREGADO|CANCELADA)$")
    notes: str | None = Field(default=None, max_length=250)


# -----------------------------------------------------------------------------
# Resenas
# -----------------------------------------------------------------------------


class ReviewCreate(BaseModel):
    product_id: int
    order_id: int
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class ReviewPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    product_id: int
    order_id: int
    rating: int
    comment: str | None
    approved: bool
    created_at: datetime


# -----------------------------------------------------------------------------
# Notificaciones
# -----------------------------------------------------------------------------


class NotificationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    message: str
    order_id: int | None
    read_at: datetime | None
    created_at: datetime


# -----------------------------------------------------------------------------
# Empleados y gastos (admin)
# -----------------------------------------------------------------------------


class EmployeeUpsert(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    document: str = Field(min_length=4, max_length=80)
    position: str = Field(min_length=2, max_length=120)
    salary: float = Field(ge=0)
    employment_status: str = Field(default="active", max_length=40)


class EmployeePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    document: str
    position: str
    salary: float
    employment_status: str


class ExpenseUpsert(BaseModel):
    expense_type: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=2, max_length=250)
    amount: float = Field(ge=0)
    observation: str | None = None
    expense_date: date


class ExpensePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    expense_type: str
    description: str
    amount: float
    observation: str | None
    expense_date: date
    created_by: int | None
    created_at: datetime


class FinanceTimeseriesPoint(BaseModel):
    label: str         # ej. "2026-05-19", "2026-05", "2026"
    gross_sales: float
    cogs: float
    orders_count: int
    gross_margin: float    # gross_sales - cogs


class FinanceSummary(BaseModel):
    period_from: date | None
    period_to: date | None
    granularity: str = "month"
    gross_sales: float
    orders_count: int
    cogs: float = 0
    gross_margin: float = 0       # gross_sales - cogs (margen bruto)
    gross_margin_pct: float = 0   # gross_margin / gross_sales * 100
    operating_expenses: float
    payroll: float
    net_profit: float             # gross_margin - operating_expenses - payroll
    net_margin_pct: float = 0     # net_profit / gross_sales * 100
    timeseries: list[FinanceTimeseriesPoint] = []
    avg_ticket: float = 0         # gross_sales / orders_count


class OrderAuditLogPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int | None
    action: str
    performed_by: int | None
    details: str | None
    correlation_id: str | None
    created_at: datetime


class ApiMessage(BaseModel):
    message: str
