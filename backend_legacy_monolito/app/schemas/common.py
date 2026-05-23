"""Esquemas Pydantic compartidos por el monolito legacy.

Define contratos de entrada y salida para autenticacion, catalogo, carrito,
checkout, pedidos, finanzas, configuracion, resenas e inventario. Estos modelos
documentan que datos acepta cada endpoint y que validaciones se aplican antes
de tocar la base de datos.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ApiMessage(BaseModel):
    """Respuesta generica para operaciones que solo devuelven confirmacion."""
    message: str


class TokenResponse(BaseModel):
    """Access token y usuario publico devueltos tras login/registro."""
    access_token: str
    token_type: str = "bearer"
    user: "UserPublic"


class UserBase(BaseModel):
    """Campos compartidos entre creacion y serializacion de usuarios."""
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: Optional[str] = None


class UserCreate(UserBase):
    """Payload de registro de cliente."""
    password: str


class UserLogin(BaseModel):
    """Credenciales requeridas para iniciar sesion."""
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """Campos editables del perfil administrativo."""
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    phone: Optional[str] = None
    active: Optional[bool] = None


class UserPublic(UserBase):
    """Vista segura de usuario, sin password_hash."""
    id: int
    role: str
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CategoryIn(BaseModel):
    """Entrada administrativa para crear o editar categorias."""
    name: str
    description: Optional[str] = None
    active: bool = True
    archived: bool = False


class ProductIn(BaseModel):
    """Entrada administrativa para productos base del catalogo."""
    category_id: int
    name: str
    description: str
    long_description: Optional[str] = None
    base_price: Decimal
    published: bool = True
    archived: bool = False
    image_url: Optional[str] = None


class VariantIn(BaseModel):
    """Entrada administrativa para una variante con costo, precio y stock."""
    sku: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    custom_attribute: Optional[str] = None
    cost: Decimal
    price: Decimal
    stock: int = Field(ge=0)
    reserved_stock: int = Field(default=0, ge=0)
    active: bool = True


class CartItemIn(BaseModel):
    """Solicitud para agregar una variante al carrito."""
    variant_id: int
    quantity: int = Field(gt=0)


class CartItemUpdate(BaseModel):
    """Solicitud para cambiar la cantidad de un item del carrito."""
    quantity: int = Field(gt=0)


class CheckoutIn(BaseModel):
    """Datos de entrega, facturacion y ajustes de total del checkout."""
    delivery_name: str
    delivery_address: str
    delivery_city: str
    billing_document: str
    contact_phone: str
    contact_email: EmailStr
    discount: Decimal = Decimal("0")
    additional_costs: Decimal = Decimal("0")


class PaymentSimulateIn(BaseModel):
    """Entrada del simulador local de pagos del monolito."""
    amount: Decimal
    requested_status: str = Field(default="aprobado", pattern="^(aprobado|rechazado|pendiente)$")


class OrderCreate(CheckoutIn):
    """Payload final para crear una orden luego de simular el pago."""
    payment_status: str = Field(pattern="^(aprobado|rechazado|pendiente)$")
    transaction_reference: str
    response_message: Optional[str] = None


class OrderStatusUpdate(BaseModel):
    """Cambio de estado logistico de una orden."""
    status: str


class EmployeeIn(BaseModel):
    """Datos administrativos para nomina."""
    name: str
    document: str
    position: str
    salary: Decimal
    employment_status: str = "active"


class ExpenseIn(BaseModel):
    """Gasto operativo que impacta reportes financieros."""
    expense_type: str
    description: str
    amount: Decimal
    observation: Optional[str] = None
    expense_date: date


class SettingsIn(BaseModel):
    """Configuracion visual/comercial editable desde administracion."""
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
    """Mensaje informativo con estado y ventana opcional de vigencia."""
    title: str
    content: str
    type: str = "info"
    active: bool = True
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ReviewIn(BaseModel):
    """Resena enviada por un cliente para un producto comprado."""
    product_id: int
    order_id: int
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None


class InventoryMovementIn(BaseModel):
    """Movimiento manual de inventario: entrada, salida o ajuste."""
    variant_id: int
    movement_type: str = Field(pattern="^(entrada|salida|ajuste)$")
    quantity: int = Field(gt=0)
    reason: str


TokenResponse.model_rebuild()

