"""Mock de pasarela de pago externa.

Simula tres tipos de respuesta:
- Si el monto termina en .00 -> APPROVED
- Si el monto termina en .77 -> REJECTED
- Si el monto termina en .99 -> PENDING (simula timeout / sin respuesta)
- Caso contrario -> APPROVED por defecto

Esto permite al Payment Service ejercitar el Circuit Breaker y las
compensaciones de la SAGA sin depender de un proveedor externo real.
"""
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Tienda Digital - Pasarela mock", version="0.1.0")


class ChargeRequest(BaseModel):
    """Contrato de cobro que Payment Service envia a la pasarela mock."""
    order_code: str
    amount: float
    currency: str = "COP"
    card_token: str | None = None


class ChargeResponse(BaseModel):
    """Respuesta simulada de la pasarela externa."""
    transaction_reference: str
    status: str  # APPROVED, REJECTED, PENDING
    message: str


@app.get("/health")
def health() -> dict:
    """Healthcheck simple para docker-compose y pruebas de conectividad."""
    return {"status": "ok", "service": "payment-mock"}


@app.post("/charge", response_model=ChargeResponse)
def charge(req: ChargeRequest) -> ChargeResponse:
    """Simula un cobro deterministico segun los centavos del monto."""
    cents = int(round(req.amount * 100)) % 100
    if cents == 77:
        return ChargeResponse(
            transaction_reference=f"mock-{uuid4().hex[:10]}",
            status="REJECTED",
            message="Tarjeta rechazada por el emisor (simulado).",
        )
    if cents == 99:
        # Simulamos demora larga devolviendo PENDING; el cliente debe interpretar.
        return ChargeResponse(
            transaction_reference=f"mock-{uuid4().hex[:10]}",
            status="PENDING",
            message="Transaccion en revision por la pasarela (simulado).",
        )
    if cents == 88:
        # Forzar un 500 para probar Circuit Breaker
        raise HTTPException(status_code=500, detail="Error interno simulado de la pasarela.")
    return ChargeResponse(
        transaction_reference=f"mock-{uuid4().hex[:10]}",
        status="APPROVED",
        message="Pago aprobado (simulado).",
    )
