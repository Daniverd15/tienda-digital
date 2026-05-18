"""Scheduler interno: libera reservas vencidas cada minuto.

Materializa la garantia del informe Fase 1, seccion 13.1:
'si el pago no se confirma antes de vencer la reserva, el stock se libera'.
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import ProductVariant, StockMovement, StockReservation

logger = logging.getLogger(__name__)


def expire_pending_reservations() -> int:
    """Marca como EXPIRED las reservas vencidas y libera el stock reservado."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        pending = (
            db.execute(
                select(StockReservation)
                .where(StockReservation.status == "PENDING")
                .where(StockReservation.expires_at <= now)
            )
            .scalars()
            .all()
        )
        if not pending:
            return 0
        for r in pending:
            v = db.query(ProductVariant).filter(ProductVariant.id == r.variant_id).with_for_update().first()
            if v:
                v.reserved_stock = max(0, v.reserved_stock - r.quantity)
                db.add(StockMovement(
                    variant_id=v.id,
                    movement_type="expire",
                    quantity=r.quantity,
                    reason=f"Reserva {r.id} expiro (order {r.order_id})",
                    order_id=r.order_id,
                ))
            r.status = "EXPIRED"
        db.commit()
        logger.info("Scheduler: %d reservas expiradas liberadas", len(pending))
        return len(pending)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Scheduler fallo: %s", exc)
        db.rollback()
        return 0
    finally:
        db.close()


async def run_scheduler_forever(interval_seconds: int = 60) -> None:
    """Tarea de fondo del lifespan."""
    logger.info("Scheduler de expiracion iniciado (cada %ds)", interval_seconds)
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            expire_pending_reservations()
        except asyncio.CancelledError:
            logger.info("Scheduler detenido")
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Scheduler error no manejado: %s", exc)
