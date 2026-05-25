"""Pydantic schemas del Auth Service."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# -----------------------------------------------------------------------------
# Entradas
# -----------------------------------------------------------------------------


class UserCreate(BaseModel):
    """Payload de registro de cliente."""
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Credenciales de inicio de sesion."""
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """Cliente actualiza sus datos basicos (nombre, telefono)."""

    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=40)


class AdminProfileUpdate(BaseModel):
    """Admin actualiza su propio perfil + opcionalmente cambia contrasena."""

    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    """Refresh token que se rota para emitir un nuevo par de tokens."""
    refresh_token: str


# -----------------------------------------------------------------------------
# Salidas
# -----------------------------------------------------------------------------


class UserPublic(BaseModel):
    """Vista publica segura de un usuario autenticado."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    phone: str | None
    role: str
    active: bool
    created_at: datetime
    updated_at: datetime


class CustomerPublic(BaseModel):
    """Vista reducida que Commerce consume para enriquecer pedidos."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    phone: str | None
    active: bool


class TokenResponse(BaseModel):
    """Par de tokens y usuario devueltos por register/login/refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in_minutes: int
    user: UserPublic


class AccessLogPublic(BaseModel):
    """Evento de acceso visible para auditoria administrativa."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    action: str
    ip: str | None
    correlation_id: str | None
    created_at: datetime


class ApiMessage(BaseModel):
    """Respuesta generica de confirmacion."""
    message: str
