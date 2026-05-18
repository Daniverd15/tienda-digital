"""Inbox de notificaciones del cliente."""
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
    db.query(Notification).filter(
        Notification.user_id == user_id, Notification.read_at.is_(None)
    ).update({Notification.read_at: datetime.utcnow()})
    db.commit()
    return ApiMessage(message="Todas las notificaciones fueron marcadas como leidas.")
