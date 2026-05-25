"""Inbox de notificaciones del cliente.

================================================================================
PROPOSITO
================================================================================
Permite al cliente consultar las notificaciones que el sistema le ha enviado
(eventos del pedido: confirmacion de compra, cambios de estado, etc.) y
marcarlas como leidas.

Las notificaciones se INSERTAN automaticamente desde:
  - checkout_saga.py al confirmar un pedido o al rechazar uno.
  - admin.py al cambiar el estado de un pedido (preparacion, envio, entrega).

Endpoints:
  GET    /notifications                → listado (opcional: only_unread=true)
  PATCH  /notifications/{id}/read      → marca una como leida
  PATCH  /notifications/read-all       → marca todas como leidas
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import current_user_id
from app.models import Notification
from app.schemas import ApiMessage, NotificationPublic


router = APIRouter(prefix="/notifications", tags=["Notificaciones"])


@router.get("", response_model=list[NotificationPublic])
def list_notifications(
    only_unread: bool = False,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    """Lista las notificaciones del usuario, mas recientes primero.

    Parametros:
        only_unread: si True, devuelve solo las que tienen read_at=None.

    Limite de 200 entradas para evitar respuestas gigantes. La paginacion
    propiamente dicha queda como TODO si crece el volumen.
    """
    q = db.query(Notification).filter(Notification.user_id == user_id)
    if only_unread:
        q = q.filter(Notification.read_at.is_(None))
    return q.order_by(Notification.id.desc()).limit(200).all()


@router.patch("/{notification_id}/read", response_model=ApiMessage)
def mark_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    """Marca una notificacion especifica como leida (setea read_at=now()).

    Filtro por user_id para evitar que un cliente marque notificaciones ajenas.
    """
    n = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user_id)
        .first()
    )
    if not n:
        raise HTTPException(404, "Notificacion no encontrada.")
    n.read_at = datetime.utcnow()
    db.commit()
    return ApiMessage(message="Notificacion marcada como leida.")


@router.patch("/read-all", response_model=ApiMessage)
def mark_all_as_read(
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    """Marca TODAS las notificaciones no leidas del usuario como leidas.

    Usa UPDATE masivo (no iteracion) por eficiencia. Util para el boton
    "marcar todo como leido" del frontend.
    """
    db.query(Notification).filter(
        Notification.user_id == user_id, Notification.read_at.is_(None)
    ).update({Notification.read_at: datetime.utcnow()})
    db.commit()
    return ApiMessage(message="Todas las notificaciones fueron marcadas como leidas.")
