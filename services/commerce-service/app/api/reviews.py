"""Endpoints de resenas (RF-21 del SRS).

Regla: solo se permite resenar productos comprados y entregados.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import current_user_id, get_correlation_id, get_current_user_token
from app.models import Order, OrderItem, Review
from app.schemas import ApiMessage, ReviewCreate, ReviewPublic
from app.services.http_clients import catalog_update_rating


router = APIRouter(prefix="/reviews", tags=["Resenas"])


def _eligible_for_review(db: Session, user_id: int, order_id: int, product_id: int) -> bool:
    """El usuario puede resenar producto X si tiene un pedido ENTREGADO con ese product_id."""
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == user_id, Order.status == "ENTREGADO")
        .first()
    )
    if not order:
        return False
    item = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == order.id, OrderItem.product_id == product_id)
        .first()
    )
    return item is not None


def _refresh_rating_in_catalog(db: Session, product_id: int, token: str, correlation_id: str | None) -> None:
    """Recalcula y envia el nuevo rating a Catalog (Cache-Aside)."""
    rows = db.query(Review).filter(
        Review.product_id == product_id, Review.approved.is_(True)
    ).all()
    if not rows:
        avg, count = 0.0, 0
    else:
        avg = round(sum(r.rating for r in rows) / len(rows), 2)
        count = len(rows)
    catalog_update_rating(product_id, avg, count, token=token, correlation_id=correlation_id)


@router.post("", response_model=ReviewPublic, status_code=status.HTTP_201_CREATED)
def create_review(
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
    token: str = Depends(get_current_user_token),
    correlation_id: str = Depends(get_correlation_id),
):
    if not _eligible_for_review(db, user_id, payload.order_id, payload.product_id):
        raise HTTPException(409, "Solo puedes resenar productos comprados y entregados.")
    existing = (
        db.query(Review)
        .filter(Review.user_id == user_id, Review.product_id == payload.product_id,
                Review.order_id == payload.order_id)
        .first()
    )
    if existing:
        raise HTTPException(409, "Ya resenaste este producto para este pedido.")
    r = Review(
        user_id=user_id, product_id=payload.product_id, order_id=payload.order_id,
        rating=payload.rating, comment=payload.comment, approved=True,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    # Notificar a Catalog para que actualice su RatingSummary
    _refresh_rating_in_catalog(db, payload.product_id, token, correlation_id)
    return r


@router.get("/mine", response_model=list[ReviewPublic])
def list_my_reviews(
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    return db.query(Review).filter(Review.user_id == user_id).order_by(Review.id.desc()).all()


@router.get("/product/{product_id}", response_model=list[ReviewPublic])
def list_reviews_of_product(product_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Review)
        .filter(Review.product_id == product_id, Review.approved.is_(True))
        .order_by(Review.created_at.desc())
        .all()
    )
