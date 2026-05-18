"""Pydantic schemas del Inventory Service."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# -----------------------------------------------------------------------------
# Variantes (vista publica para clientes y Catalog)
# -----------------------------------------------------------------------------


class VariantPublic(BaseModel):
    """Vista publica de una variante: lo que Catalog necesita para enriquecer detalle."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    sku: str
    color: str | None
    size: str | None
    custom_attribute: str | None
    price: float
    available: int          # stock - reserved
    active: bool


class VariantInternal(BaseModel):
    """Vista interna con datos sensibles (cost, stock total)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    sku: str
    color: str | None
    size: str | None
    custom_attribute: str | None
    cost: float
    price: float
    stock: int
    reserved_stock: int
    available: int
    active: bool
    created_at: datetime
    updated_at: datetime


class VariantAdminCreate(BaseModel):
    product_id: int = Field(gt=0)
    sku: str = Field(min_length=2, max_length=80)
    color: str | None = Field(default=None, max_length=80)
    size: str | None = Field(default=None, max_length=80)
    custom_attribute: str | None = Field(default=None, max_length=160)
    cost: float = Field(ge=0)
    price: float = Field(ge=0)
    stock: int = Field(default=0, ge=0)
    active: bool = True


class VariantAdminUpdate(BaseModel):
    sku: str | None = Field(default=None, min_length=2, max_length=80)
    color: str | None = None
    size: str | None = None
    custom_attribute: str | None = None
    cost: float | None = Field(default=None, ge=0)
    price: float | None = Field(default=None, ge=0)
    active: bool | None = None


# -----------------------------------------------------------------------------
# Reservas (consumido por Commerce durante el checkout)
# -----------------------------------------------------------------------------


class ReserveItem(BaseModel):
    variant_id: int
    quantity: int = Field(ge=1)


class ReserveRequest(BaseModel):
    order_id: str = Field(min_length=1, max_length=60)
    items: list[ReserveItem]
    ttl_seconds: int = Field(default=900, ge=60, le=3600)  # 15 min por defecto


class ReservedLineResult(BaseModel):
    variant_id: int
    sku: str
    quantity: int
    unit_price: float
    line_total: float


class ReserveResponse(BaseModel):
    order_id: str
    reservation_ids: list[int]
    expires_at: datetime
    items: list[ReservedLineResult]
    subtotal: float


class ReleaseRequest(BaseModel):
    order_id: str
    reason: str = Field(default="manual_release", max_length=120)


# -----------------------------------------------------------------------------
# Movimientos (manual desde admin: entrada de stock, ajuste, salida)
# -----------------------------------------------------------------------------


class StockMovementUpsert(BaseModel):
    variant_id: int
    movement_type: str = Field(pattern="^(entry|adjust|exit)$")
    quantity: int  # puede ser negativo para ajustes
    reason: str = Field(min_length=1, max_length=250)


class StockMovementPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    variant_id: int
    movement_type: str
    quantity: int
    reason: str
    user_id: int | None
    order_id: str | None
    correlation_id: str | None
    created_at: datetime


# -----------------------------------------------------------------------------
# Alertas
# -----------------------------------------------------------------------------


class LowStockAlertPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    variant_id: int
    product_id: int | None = None
    product_name: str | None = None
    sku: str | None = None
    stock: int | None = None
    available: int | None = None
    threshold: int
    stock_at_alert: int
    resolved: bool
    notes: str | None
    created_at: datetime


# -----------------------------------------------------------------------------
# Mensajes
# -----------------------------------------------------------------------------


class ApiMessage(BaseModel):
    message: str
