"""Scheduler interno del Inventory Service: libera reservas vencidas.

================================================================================
PROPOSITO
================================================================================
Materializa la garantia del informe Fase 1, seccion 13.1:
"si el pago no se confirma antes de vencer la reserva, el stock se libera".

Cuando un cliente inicia checkout, Inventory crea una StockReservation con
status=PENDING y expires_at = now() + 15 minutos. Si el cliente abandona el
checkout o el SAGA falla sin liberar, esta reserva quedaria "reservada para
siempre" bloqueando stock para otros clientes.

El scheduler asincrono corre cada 60s (configurable via interval_seconds) y:
  1. Busca reservas con status=PENDING y expires_at <= now()
  2. Por cada una: libera el reserved_stock de la variante y marca EXPIRED
  3. Registra un StockMovement de tipo "expire" para auditoria

================================================================================
INTEGRACION CON FastAPI
================================================================================
Se monta como tarea de background dentro del `lifespan` de la app (en main.py):

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(run_scheduler_forever(60))
        yield
        task.cancel()  # se detiene limpio al apagar el servicio

Esto evita correr un proceso separado (cron) y mantiene todo en el mismo
contenedor del servicio.

================================================================================
USO MANUAL
================================================================================
Tambien se expone como endpoint admin POST /admin/expire-pending para que
los tests de chaos puedan disparar la limpieza sin esperar al ciclo
automatico de 60s.
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import ProductVariant, StockMovement, StockReservation

logger = logging.getLogger(__name__)


def expire_pending_reservations() -> int:
    """Marca como EXPIRED las reservas vencidas y libera el reserved_stock.

    Devuelve la cantidad de reservas procesadas (0 si no habia ninguna
    vencida). Es seguro llamarla concurrentemente: usa SELECT FOR UPDATE
    sobre las variantes para evitar race conditions con un POST /reserve
    que este ocurriendo en paralelo.

    Flujo interno:
    1. SELECT reservas con status=PENDING y expires_at <= now (UTC).
    2. Para cada reserva:
       a) SELECT FOR UPDATE sobre la variante asociada (lock pesimista MySQL).
       b) Decrementa reserved_stock en la variante (libera el bloqueo logico).
       c) Crea un StockMovement de tipo "expire" para auditoria.
       d) Marca la reserva con status=EXPIRED.
    3. COMMIT atomico de TODAS las reservas en una sola transaccion.

    Si algo falla, ROLLBACK total y se reintenta en el proximo ciclo
    (idempotente: una reserva expirada que no se llego a marcar volveria
    a entrar en el filtro la proxima vez).
    """
    db = SessionLocal()
    try:
        # Trabajamos en UTC porque MySQL guarda los datetimes como naive UTC.
        # replace(tzinfo=None) quita el tzinfo para que la comparacion con
        # expires_at funcione sin warning de SQLAlchemy.
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Buscamos TODAS las reservas vencidas en una sola query.
        # No usamos .with_for_update() aqui porque queremos solo el listado;
        # el lock real se toma fila a fila dentro del loop sobre las variantes.
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
            # Lock pesimista sobre la variante para evitar que un POST /reserve
            # concurrente lea un valor obsoleto de reserved_stock y sobreescriba.
            # MySQL: SELECT ... FOR UPDATE.
            v = (
                db.query(ProductVariant)
                .filter(ProductVariant.id == r.variant_id)
                .with_for_update()
                .first()
            )
            if v:
                # Liberamos el stock reservado. max(0, ...) defensivo: por si
                # algun bug previo hizo reserved_stock < quantity, no queremos
                # quedar con negativos.
                v.reserved_stock = max(0, v.reserved_stock - r.quantity)
                # Registramos el movimiento para que el admin pueda ver
                # exactamente cuando se libero por timeout vs por compensacion.
                db.add(StockMovement(
                    variant_id=v.id,
                    movement_type="expire",
                    quantity=r.quantity,
                    reason=f"Reserva {r.id} expiro (order {r.order_id})",
                    order_id=r.order_id,
                ))
            # Marcamos la reserva como EXPIRED aunque la variante no exista
            # (caso edge: variante borrada). Asi no la procesamos otra vez.
            r.status = "EXPIRED"

        db.commit()
        logger.info("Scheduler: %d reservas expiradas liberadas", len(pending))
        return len(pending)
    except Exception as exc:  # noqa: BLE001
        # Cualquier excepcion: rollback total. En el proximo ciclo se reintenta.
        logger.exception("Scheduler fallo: %s", exc)
        db.rollback()
        return 0
    finally:
        # Cierre defensivo del Session para evitar fugas de conexiones MySQL.
        db.close()


async def run_scheduler_forever(interval_seconds: int = 60) -> None:
    """Tarea de fondo del lifespan: ejecuta expire_pending_reservations cada
    `interval_seconds` segundos, indefinidamente.

    Se inicia con asyncio.create_task() en el lifespan de FastAPI y se
    cancela limpiamente cuando el servicio recibe SIGTERM (Ctrl+C o `docker
    compose down`). La cancelacion levanta asyncio.CancelledError que
    re-lanzamos para que el await asyncio.gather(task) en main.py se
    complete sin colgar el shutdown.

    Importante: el sleep va ANTES del trabajo, no despues. Asi el primer
    barrido ocurre 60s despues del startup y no inmediato (que podria
    competir con la inicializacion de la BD).
    """
    logger.info("Scheduler de expiracion iniciado (cada %ds)", interval_seconds)
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            expire_pending_reservations()
        except asyncio.CancelledError:
            # Shutdown limpio: re-lanzamos para que el await pueda completarse.
            logger.info("Scheduler detenido")
            raise
        except Exception as exc:  # noqa: BLE001
            # Errores no esperados (Redis cae, MySQL drops la conexion): los
            # logueamos pero NO rompemos el loop. El proximo ciclo intentara
            # de nuevo. Esto da resiliencia automatica.
            logger.exception("Scheduler error no manejado: %s", exc)
