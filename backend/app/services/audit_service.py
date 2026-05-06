import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import AuditLog, SystemLog


def add_audit_log(
    db: Session,
    *,
    user_id: Optional[int],
    action: str,
    entity: str,
    entity_id: Optional[Any] = None,
    previous_value: Optional[Any] = None,
    new_value: Optional[Any] = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            previous_value=json.dumps(previous_value, default=str) if previous_value is not None else None,
            new_value=json.dumps(new_value, default=str) if new_value is not None else None,
        )
    )


def add_system_log(db: Session, *, level: str, message: str, context: Optional[Any] = None) -> None:
    db.add(
        SystemLog(
            level=level,
            message=message,
            context=json.dumps(context, default=str) if context is not None else None,
        )
    )

