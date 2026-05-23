"""Schemas Payment Service."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChargeRequest(BaseModel):
    """Solicitud de cobro enviada por Commerce."""
    order_id: str = Field(min_length=1, max_length=60)
    amount: float = Field(gt=0)
    currency: str = Field(default="COP", max_length=10)
    card_token: str | None = Field(default=None, max_length=120)


class ChargeResponse(BaseModel):
    """Resultado del intento de cobro devuelto a Commerce."""
    payment_id: int
    order_id: str
    transaction_reference: str
    status: str  # APPROVED, REJECTED, PENDING, FAILED
    amount: float
    currency: str
    message: str


class PaymentPublic(BaseModel):
    """Pago persistido para seguimiento y conciliacion."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: str
    provider: str
    transaction_reference: str
    status: str
    amount: float
    currency: str
    response_message: str
    created_at: datetime
    updated_at: datetime


class RefundRequest(BaseModel):
    """Solicitud administrativa de reembolso parcial o total."""
    payment_id: int
    amount: float = Field(gt=0)
    reason: str = Field(min_length=2, max_length=250)


class ApiMessage(BaseModel):
    """Respuesta generica de confirmacion."""
    message: str
