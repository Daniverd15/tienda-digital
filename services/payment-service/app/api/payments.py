"""Endpoints de pagos. Consumido por Commerce durante checkout."""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_correlation_id, get_current_user_claims, require_admin
from app.models import Payment, PaymentAttempt, Refund
from app.schemas import ApiMessage, ChargeRequest, ChargeResponse, PaymentPublic, RefundRequest
from app.services.gateway_client import charge as gateway_charge


router = APIRouter(prefix="/payments", tags=["Pagos"])


@router.post("", response_model=ChargeResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: ChargeRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user_claims),
    correlation_id: str = Depends(get_correlation_id),
):
    """Crea un Payment para una orden y dispara el charge a la pasarela mock.

    Persiste el resultado en payments_db: si la pasarela dio APPROVED, queda
    APPROVED; si dio REJECTED/PENDING/FAILED, queda con ese estado para que
    Commerce pueda decidir (continuar la SAGA o ejecutar compensacion).
    """
    result = gateway_charge(
        order_id=payload.order_id,
        amount=payload.amount,
        currency=payload.currency,
        card_token=payload.card_token,
    )
    p = Payment(
        order_id=payload.order_id,
        provider="mock",
        transaction_reference=result["transaction_reference"],
        status=result["status"],
        amount=Decimal(str(payload.amount)),
        currency=payload.currency,
        response_message=(result.get("message") or "")[:250],
    )
    db.add(p)
    db.flush()
    db.add(PaymentAttempt(
        payment_id=p.id,
        attempt_number=1,
        provider_response=str(result),
        status=result["status"],
    ))
    db.commit()
    db.refresh(p)
    return ChargeResponse(
        payment_id=p.id,
        order_id=p.order_id,
        transaction_reference=p.transaction_reference,
        status=p.status,
        amount=float(p.amount),
        currency=p.currency,
        message=p.response_message,
    )


@router.get("/{payment_id}", response_model=PaymentPublic)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user_claims),
):
    p = db.query(Payment).filter(Payment.id == payment_id).first()
    if not p:
        raise HTTPException(404, "Pago no encontrado.")
    return p


@router.get("/by-order/{order_id}")
def get_by_order(
    order_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user_claims),
):
    rows = db.query(Payment).filter(Payment.order_id == order_id).order_by(Payment.id.desc()).all()
    return [PaymentPublic.model_validate(p).model_dump() for p in rows]


@router.post("/refund", response_model=ApiMessage)
def refund(
    payload: RefundRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    p = db.query(Payment).filter(Payment.id == payload.payment_id).first()
    if not p:
        raise HTTPException(404, "Pago no encontrado.")
    if p.status != "APPROVED":
        raise HTTPException(409, "Solo se reembolsan pagos APPROVED.")
    if payload.amount > float(p.amount):
        raise HTTPException(422, "Monto del reembolso supera el pago original.")
    r = Refund(
        payment_id=p.id, amount=Decimal(str(payload.amount)),
        reason=payload.reason, status="PROCESSED",
    )
    db.add(r)
    db.commit()
    return ApiMessage(message=f"Reembolso procesado por {payload.amount}.")
