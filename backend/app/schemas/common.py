from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ApiMessage(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserPublic"


class UserBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    phone: Optional[str] = None
    active: Optional[bool] = None


class UserPublic(UserBase):
    id: int
    role: str
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CategoryIn(BaseModel):
    name: str
    description: Optional[str] = None
    active: bool = True
    archived: bool = False


class ProductIn(BaseModel):
    category_id: int
    name: str
    description: str
    long_description: Optional[str] = None
    base_price: Decimal
    published: bool = True
    archived: bool = False
    image_url: Optional[str] = None


class VariantIn(BaseModel):
    sku: str
    color: Optional[str] = None
    size: Optional[str] = None
    custom_attribute: Optional[str] = None
    cost: Decimal
    price: Decimal
    stock: int = Field(ge=0)
    reserved_stock: int = Field(default=0, ge=0)
    active: bool = True


class CartItemIn(BaseModel):
    variant_id: int
    quantity: int = Field(gt=0)


class CartItemUpdate(BaseModel):
    quantity: int = Field(gt=0)


class CheckoutIn(BaseModel):
    delivery_name: str
    delivery_address: str
    delivery_city: str
    billing_document: str
    contact_phone: str
    contact_email: EmailStr
    discount: Decimal = Decimal("0")
    additional_costs: Decimal = Decimal("0")


class PaymentSimulateIn(BaseModel):
    amount: Decimal
    requested_status: str = Field(default="aprobado", pattern="^(aprobado|rechazado|pendiente)$")


class OrderCreate(CheckoutIn):
    payment_status: str = Field(pattern="^(aprobado|rechazado|pendiente)$")
    transaction_reference: str
    response_message: Optional[str] = None


class OrderStatusUpdate(BaseModel):
    status: str


class EmployeeIn(BaseModel):
    name: str
    document: str
    position: str
    salary: Decimal
    employment_status: str = "active"


class ExpenseIn(BaseModel):
    expense_type: str
    description: str
    amount: Decimal
    observation: Optional[str] = None
    expense_date: date


class SettingsIn(BaseModel):
    commercial_name: str
    logo_url: Optional[str] = None
    primary_color: str
    secondary_color: str
    banner_url: Optional[str] = None
    contact_email: EmailStr
    contact_phone: str
    currency: str
    stock_threshold: int = Field(gt=0)


class MessageIn(BaseModel):
    title: str
    content: str
    type: str = "info"
    active: bool = True
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ReviewIn(BaseModel):
    product_id: int
    order_id: int
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None


class InventoryMovementIn(BaseModel):
    variant_id: int
    movement_type: str = Field(pattern="^(entrada|salida|ajuste)$")
    quantity: int = Field(gt=0)
    reason: str


TokenResponse.model_rebuild()

