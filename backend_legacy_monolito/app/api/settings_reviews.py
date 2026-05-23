"""Configuracion de tienda, mensajes, auditoria y resenas del monolito.

Une varias responsabilidades administrativas del MVP inicial: branding,
mensajes informativos, moderacion de resenas, consulta de auditoria y creacion
de resenas por clientes. En microservicios estas piezas se reparten entre
Catalog Service y Commerce Service.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import require_admin, require_customer
from app.core.database import get_db
from app.models import AuditLog, InformativeMessage, Order, OrderItem, Product, Review, StoreSetting, User
from app.schemas import ApiMessage, MessageIn, ReviewIn, SettingsIn
from app.services.audit_service import add_audit_log


router = APIRouter(tags=["Configuracion y resenas"])


def serialize_setting(setting: StoreSetting) -> dict:
    """Serializa la configuracion visual y comercial de la tienda."""
    return {
        "id": setting.id,
        "commercial_name": setting.commercial_name,
        "logo_url": setting.logo_url,
        "primary_color": setting.primary_color,
        "secondary_color": setting.secondary_color,
        "banner_url": setting.banner_url,
        "contact_email": setting.contact_email,
        "contact_phone": setting.contact_phone,
        "currency": setting.currency,
        "stock_threshold": setting.stock_threshold,
    }


def serialize_message(message: InformativeMessage) -> dict:
    """Serializa mensajes informativos con su estado y ventana de vigencia."""
    return {
        "id": message.id,
        "title": message.title,
        "content": message.content,
        "type": message.type,
        "active": message.active,
        "start_date": message.start_date,
        "end_date": message.end_date,
    }


@router.get("/admin/settings")
def admin_get_settings(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Obtiene la configuracion actual para el formulario del administrador."""
    setting = db.query(StoreSetting).order_by(StoreSetting.id.asc()).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Configuracion no encontrada.")
    return serialize_setting(setting)


@router.put("/admin/settings")
def admin_update_settings(payload: SettingsIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Crea o actualiza la configuracion de tienda y registra auditoria."""
    setting = db.query(StoreSetting).order_by(StoreSetting.id.asc()).first()
    if not setting:
        setting = StoreSetting(**payload.model_dump())
        db.add(setting)
        db.flush()
    else:
        previous = serialize_setting(setting)
        for field, value in payload.model_dump().items():
            setattr(setting, field, value)
        add_audit_log(db, user_id=admin.id, action="update_settings", entity="store_settings", entity_id=setting.id, previous_value=previous, new_value=payload.model_dump())
    db.commit()
    db.refresh(setting)
    return serialize_setting(setting)


@router.get("/admin/messages")
def admin_messages(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Lista mensajes informativos administrables."""
    return [serialize_message(message) for message in db.query(InformativeMessage).order_by(InformativeMessage.id.desc()).all()]


@router.post("/admin/messages", status_code=status.HTTP_201_CREATED)
def create_message(payload: MessageIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Crea un mensaje visible para clientes segun fechas y estado activo."""
    message = InformativeMessage(**payload.model_dump())
    db.add(message)
    db.flush()
    add_audit_log(db, user_id=admin.id, action="create_message", entity="informative_messages", entity_id=message.id, new_value=payload.model_dump())
    db.commit()
    db.refresh(message)
    return serialize_message(message)


@router.put("/admin/messages/{message_id}")
def update_message(message_id: int, payload: MessageIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Edita contenido, tipo y ventana de publicacion de un mensaje."""
    message = db.query(InformativeMessage).filter(InformativeMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado.")
    previous = serialize_message(message)
    for field, value in payload.model_dump().items():
        setattr(message, field, value)
    add_audit_log(db, user_id=admin.id, action="update_message", entity="informative_messages", entity_id=message.id, previous_value=previous, new_value=payload.model_dump())
    db.commit()
    return serialize_message(message)


@router.delete("/admin/messages/{message_id}", response_model=ApiMessage)
def delete_message(message_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Desactiva un mensaje sin eliminarlo fisicamente."""
    message = db.query(InformativeMessage).filter(InformativeMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado.")
    message.active = False
    add_audit_log(db, user_id=admin.id, action="deactivate_message", entity="informative_messages", entity_id=message.id)
    db.commit()
    return ApiMessage(message="Mensaje desactivado.")


@router.get("/admin/reviews")
def admin_reviews(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Lista resenas para moderacion administrativa."""
    reviews = db.query(Review).order_by(Review.id.desc()).all()
    return [
        {
            "id": r.id,
            "product_id": r.product_id,
            "order_id": r.order_id,
            "user_id": r.user_id,
            "rating": r.rating,
            "comment": r.comment,
            "approved": r.approved,
            "created_at": r.created_at,
        }
        for r in reviews
    ]


@router.patch("/admin/reviews/{review_id}")
def update_review_status(review_id: int, approved: bool, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Aprueba o rechaza la visibilidad publica de una resena."""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Reseña no encontrada.")
    review.approved = approved
    add_audit_log(db, user_id=admin.id, action="update_review_approval", entity="reviews", entity_id=review.id, new_value={"approved": approved})
    db.commit()
    return {"id": review.id, "approved": review.approved}


@router.get("/admin/audit-logs")
def audit_logs(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Expone los ultimos eventos de auditoria para trazabilidad."""
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "entity": log.entity,
            "entity_id": log.entity_id,
            "previous_value": log.previous_value,
            "new_value": log.new_value,
            "created_at": log.created_at,
        }
        for log in logs
    ]


@router.post("/reviews", status_code=status.HTTP_201_CREATED)
def create_review(payload: ReviewIn, current_user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Permite resenar solo productos comprados y entregados por el cliente."""
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    order = (
        db.query(Order)
        .options(joinedload(Order.items).joinedload(OrderItem.variant))
        .filter(Order.id == payload.order_id, Order.user_id == current_user.id)
        .first()
    )
    if not order or order.status != "entregado" or order.payment_status != "aprobado":
        raise HTTPException(status_code=403, detail="Solo puedes resenar productos comprados y entregados.")
    bought_product = any(item.variant.product_id == payload.product_id for item in order.items)
    if not bought_product:
        raise HTTPException(status_code=403, detail="El producto no pertenece al pedido entregado.")
    existing = (
        db.query(Review)
        .filter(Review.user_id == current_user.id, Review.product_id == payload.product_id, Review.order_id == payload.order_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe una resena para este producto y pedido.")
    review = Review(user_id=current_user.id, approved=True, **payload.model_dump())
    db.add(review)
    db.flush()
    add_audit_log(db, user_id=current_user.id, action="create_review", entity="reviews", entity_id=review.id, new_value=payload.model_dump())
    db.commit()
    db.refresh(review)
    return {
        "id": review.id,
        "product_id": review.product_id,
        "order_id": review.order_id,
        "rating": review.rating,
        "comment": review.comment,
        "approved": review.approved,
    }

