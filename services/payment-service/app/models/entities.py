"""Bounded context Payments."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    order_id = Column(String(60), nullable=False, index=True)  # ref logica a Commerce
    provider = Column(String(80), nullable=False, default="mock")
    transaction_reference = Column(String(120), nullable=False)
    status = Column(String(40), nullable=False)  # APPROVED, REJECTED, PENDING, FAILED
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="COP")
    response_message = Column(String(250), nullable=False, default="")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    attempts = relationship("PaymentAttempt", back_populates="payment",
                            cascade="all, delete-orphan")
    refunds = relationship("Refund", back_populates="payment",
                           cascade="all, delete-orphan")


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"

    id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False, default=1)
    provider_response = Column(Text, nullable=True)
    status = Column(String(40), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    payment = relationship("Payment", back_populates="attempts")


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    reason = Column(String(250), nullable=False)
    status = Column(String(40), nullable=False, default="PROCESSED")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    payment = relationship("Payment", back_populates="refunds")
