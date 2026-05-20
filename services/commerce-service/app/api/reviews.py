"""Endpoints de reseñas (RF-09 del SRS).

================================================================================
PROPOSITO
================================================================================
Permite a los clientes reseñar productos que efectivamente compraron y
recibieron. Implementa el "compra verificada" del informe Fase 1.

Reglas de negocio:
  - Solo se puede reseñar productos comprados y entregados (status=ENTREGADO).
  - Una reseña por (user_id, product_id, order_id) — no se permite editar.
  - Las reseñas entran como PENDIENTES (approved=False) y requieren
    aprobacion del admin antes de mostrarse al publico.
  - Cuando admin aprueba, Commerce recalcula el rating promedio y notifica
    al Catalog Service para que actualice su RatingSummary cacheado.

Endpoints:
  POST   /reviews                  → crear reseña (entra pendiente)
  GET    /reviews/mine             → mis reseñas (todas, aprobadas y pendientes)
  GET    /reviews/product/{id}     → reseñas APROBADAS de un producto (publico)
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
    """Valida que el usuario tenga el derecho de reseñar `product_id`.

    Reglas:
      1. Debe existir un pedido del usuario con ese order_id.
      2. El pedido debe estar en estado ENTREGADO (no en preparacion, no enviado).
      3. El pedido debe contener el product_id en sus OrderItems.

    Devuelve True si TODAS se cumplen. False en cualquier otro caso (que
    el caller traduce a 409 con mensaje "solo puedes reseñar productos
    comprados y entregados").
    """
    # 1+2. Pedido propio en estado ENTREGADO.
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == user_id, Order.status == "ENTREGADO")
        .first()
    )
    if not order:
        return False
    # 3. El producto debe estar en alguno de los OrderItems del pedido.
    item = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == order.id, OrderItem.product_id == product_id)
        .first()
    )
    return item is not None


def _refresh_rating_in_catalog(db: Session, product_id: int, token: str, correlation_id: str | None) -> None:
    """Recalcula el rating promedio de un producto y se lo notifica a Catalog.

    Lo invoca el admin DESDE el endpoint /admin/reviews/{id}/approve (ver
    api/admin.py) cuando aprueba o rechaza una reseña. Catalog actualiza
    su RatingSummary y rompe el cache para que la nueva calificacion
    aparezca inmediato en la ficha publica.

    Calcula avg con round(2) y excluye reseñas no aprobadas (solo cuentan
    las moderadas). Si no hay reseñas aprobadas → avg=0, count=0.
    """
    rows = db.query(Review).filter(
        Review.product_id == product_id, Review.approved.is_(True)
    ).all()
    if not rows:
        avg, count = 0.0, 0
    else:
        avg = round(sum(r.rating for r in rows) / len(rows), 2)
        count = len(rows)
    # Llamada HTTP cross-service: si Catalog cae, el cliente recibira la
    # reseña creada igual; el rating se sincronizara cuando Catalog vuelva.
    catalog_update_rating(product_id, avg, count, token=token, correlation_id=correlation_id)


@router.post("", response_model=ReviewPublic, status_code=status.HTTP_201_CREATED)
def create_review(
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
    token: str = Depends(get_current_user_token),
    correlation_id: str = Depends(get_correlation_id),
):
    """Crea una reseña pendiente de aprobacion.

    Body: {order_id, product_id, rating (1-5), comment}

    Validaciones:
      - 409 si el cliente no tiene el pedido entregado con ese producto.
      - 409 si ya hay una reseña previa para (user, product, order).

    La reseña entra con approved=False. NO se recalcula el rating en
    Catalog hasta que el admin la apruebe.
    """
    # ─── Validacion 1: derecho a reseñar ────────────────────────────────
    if not _eligible_for_review(db, user_id, payload.order_id, payload.product_id):
        raise HTTPException(409, "Solo puedes resenar productos comprados y entregados.")

    # ─── Validacion 2: una sola reseña por (user, product, order) ───────
    existing = (
        db.query(Review)
        .filter(Review.user_id == user_id, Review.product_id == payload.product_id,
                Review.order_id == payload.order_id)
        .first()
    )
    if existing:
        raise HTTPException(409, "Ya resenaste este producto para este pedido.")

    # ─── Crear la reseña en estado PENDIENTE ────────────────────────────
    # IMPORTANTE: approved=False obliga a que pase por moderacion admin
    # antes de mostrarse al publico. Esto fue una correccion de bug
    # (antes entraban como approved=True automaticamente).
    r = Review(
        user_id=user_id, product_id=payload.product_id, order_id=payload.order_id,
        rating=payload.rating, comment=payload.comment, approved=False,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    # NO recalculamos rating en Catalog aqui — solo se hace cuando admin
    # aprueba (en api/admin.py).
    return r


@router.get("/mine", response_model=list[ReviewPublic])
def list_my_reviews(
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    """Lista TODAS las reseñas del usuario (incluidas las pendientes).

    El frontend la usa en OrderDetail para mostrar qué productos del pedido
    ya tienen reseña del cliente (sea aprobada o pendiente).
    """
    return db.query(Review).filter(Review.user_id == user_id).order_by(Review.id.desc()).all()


@router.get("/product/{product_id}", response_model=list[ReviewPublic])
def list_reviews_of_product(product_id: int, db: Session = Depends(get_db)):
    """Lista las reseñas APROBADAS de un producto (endpoint publico).

    No requiere autenticacion: cualquiera que vea la ficha del producto en
    la tienda puede ver las opiniones de otros clientes. Solo las aprobadas
    (filtro approved=True) — las pendientes son invisibles al publico.
    """
    return (
        db.query(Review)
        .filter(Review.product_id == product_id, Review.approved.is_(True))
        .order_by(Review.created_at.desc())
        .all()
    )
