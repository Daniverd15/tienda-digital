"""Worker async de reconciliacion (informe Fase 1, seccion 13.1).

Cada N segundos revisa pagos PENDING/FAILED creados hace mas de un umbral
y reintenta el cargo. Si el CB esta abierto, no hace nada esta iteracion.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.core.database import SessionLocal
from app.models import Payment, PaymentAttempt
from app.services.gateway_client import CircuitOpenError, charge as gateway_charge, provider_cb

logger = logging.getLogger(__name__)


def reconcile_once(older_than_seconds: int = 30, batch: int = 20) -> int:
    """Reconcilia hasta `batch` pagos PENDING/FAILED creados hace `older_than_seconds`+."""
    if provider_cb.get_state().value == "OPEN":
        logger.info("Reconciler: CB OPEN, posponiendo iteracion.")
        return 0
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=older_than_seconds)
    db = SessionLocal()
    processed = 0
    try:
        pendings = (
            db.query(Payment)
            .filter(Payment.status.in_(["PENDING", "FAILED"]))
            .filter(Payment.updated_at <= cutoff)
            .order_by(Payment.id.asc())
            .limit(batch)
            .all()
        )
        for p in pendings:
            try:
                result = gateway_charge(
                    order_id=p.order_id, amount=float(p.amount), currency=p.currency,
                )
            except CircuitOpenError:
                logger.info("Reconciler: CB se abrio durante el batch, paramos.")
                break
            next_attempt = (
                db.query(PaymentAttempt).filter(PaymentAttempt.payment_id == p.id).count()
            ) + 1
            db.add(PaymentAttempt(
                payment_id=p.id, attempt_number=next_attempt,
                provider_response=str(result), status=result["status"],
            ))
            p.status = result["status"]
            p.transaction_reference = result["transaction_reference"]
            p.response_message = (result.get("message") or "")[:250]
            processed += 1
        db.commit()
        if processed:
            logger.info("Reconciler procesado %d pagos.", processed)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Reconciler fallo: %s", exc)
        db.rollback()
    finally:
        db.close()
    return processed


async def run_reconciler_forever(interval_seconds: int = 300) -> None:
    logger.info("Reconciler async iniciado (cada %ds).", interval_seconds)
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            reconcile_once()
        except asyncio.CancelledError:
            logger.info("Reconciler detenido.")
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Reconciler loop error: %s", exc)
