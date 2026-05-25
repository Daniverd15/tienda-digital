"""Worker asincrono de reconciliacion de pagos (informe Fase 1, seccion 13.1).

================================================================================
PROPOSITO
================================================================================
Cuando un pago queda en estado PENDING o FAILED (porque la pasarela timeo,
respondio 5xx o el Circuit Breaker se abrio), no podemos saber con certeza
si la pasarela proceso el cobro o no. El reconciler corre cada N segundos y
reintenta esos pagos para resolver la incertidumbre:

  - Si la pasarela ya cobro al cliente y devuelve APPROVED → marcamos PAID.
  - Si la pasarela no cobro y rechaza → marcamos REJECTED (compensacion).
  - Si la pasarela sigue inestable → dejamos PENDING para el proximo ciclo.

Esto evita dos escenarios catastroficos:
  1. Cliente cobrado dos veces (el reconciler usa el mismo order_id, la
     pasarela es idempotente).
  2. Cliente cobrado y sin pedido (el reconciler eventualmente actualiza el
     estado a APPROVED y Commerce puede consultarlo).

================================================================================
DETALLES OPERATIVOS
================================================================================
- Solo reintenta pagos creados/actualizados hace mas de `older_than_seconds`
  (default 30s) para no atropellar pagos recien intentados que aun pueden
  resolverse por flujo normal.
- Procesa en batches (default 20) para evitar bloquear muchos recursos.
- Si el Circuit Breaker esta OPEN al inicio del ciclo, no hace nada esta
  iteracion (no tiene sentido golpear una pasarela que ya sabemos caida).
- Si el CB se abre durante el batch, se detiene el procesamiento.
- Cada reintento genera un PaymentAttempt para auditoria (numero de intento,
  respuesta de la pasarela, status resultante).

================================================================================
INTEGRACION
================================================================================
Se monta como tarea de background en el lifespan de FastAPI:

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(run_reconciler_forever(300))
        yield
        task.cancel()
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.core.database import SessionLocal
from app.models import Payment, PaymentAttempt
from app.services.gateway_client import CircuitOpenError, charge as gateway_charge, provider_cb

logger = logging.getLogger(__name__)


def reconcile_once(older_than_seconds: int = 30, batch: int = 20) -> int:
    """Reintenta una vez hasta `batch` pagos PENDING/FAILED.

    Parametros:
        older_than_seconds: solo procesa pagos cuya `updated_at` sea anterior
                            a `now - older_than_seconds`. Default 30s — da
                            tiempo a que un pago recien creado se resuelva
                            por flujo normal antes de que el reconciler intervenga.
        batch: cantidad maxima de pagos a procesar por iteracion. Default 20.

    Devuelve la cantidad de pagos efectivamente procesados (puede ser 0 si
    no habia pendientes, si el CB esta abierto o si se rompio el batch).

    Es seguro llamarla manualmente desde tests o desde el endpoint admin
    POST /payments/{id}/reconcile.
    """
    # ─── 1. Si el CB esta abierto, no hace sentido reintentar nada ────────
    if provider_cb.get_state().value == "OPEN":
        logger.info("Reconciler: CB OPEN, posponiendo iteracion.")
        return 0

    # ─── 2. Calcular cutoff temporal y abrir sesion DB ────────────────────
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=older_than_seconds)
    db = SessionLocal()
    processed = 0
    try:
        # Buscamos pagos PENDING/FAILED viejos, en orden FIFO (id ASC).
        # No usamos FOR UPDATE porque la concurrencia entre reconcilers es baja
        # (solo hay un proceso de reconciler por instancia del servicio) y
        # un eventual reintento duplicado seria absorbido por la idempotencia
        # de la pasarela.
        pendings = (
            db.query(Payment)
            .filter(Payment.status.in_(["PENDING", "FAILED"]))
            .filter(Payment.updated_at <= cutoff)
            .order_by(Payment.id.asc())
            .limit(batch)
            .all()
        )

        for p in pendings:
            # ─── 3. Intentar cobrar de nuevo a la pasarela ────────────────
            try:
                result = gateway_charge(
                    order_id=p.order_id, amount=float(p.amount), currency=p.currency,
                )
            except CircuitOpenError:
                # Si el CB se abrio durante el batch (porque algun pago de los
                # anteriores fallo), no tiene sentido seguir intentando.
                logger.info("Reconciler: CB se abrio durante el batch, paramos.")
                break

            # ─── 4. Registrar el intento en la bitacora de PaymentAttempt ─
            # Calculamos el numero de intento sumando los previos.
            next_attempt = (
                db.query(PaymentAttempt).filter(PaymentAttempt.payment_id == p.id).count()
            ) + 1
            db.add(PaymentAttempt(
                payment_id=p.id, attempt_number=next_attempt,
                provider_response=str(result), status=result["status"],
            ))

            # ─── 5. Actualizar el estado del Payment ──────────────────────
            # Truncamos response_message a 250 chars para que entre en el VARCHAR
            # de la tabla Payment.
            p.status = result["status"]
            p.transaction_reference = result["transaction_reference"]
            p.response_message = (result.get("message") or "")[:250]
            processed += 1

        # Commit unico de TODOS los pagos procesados en una transaccion.
        # Si algo falla a mitad, ROLLBACK total y se reintenta en el proximo ciclo.
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
    """Loop infinito que ejecuta reconcile_once() cada `interval_seconds`.

    Se inicia con asyncio.create_task() en el lifespan de FastAPI y se
    cancela limpiamente al apagar el servicio (SIGTERM / docker compose down).

    Default 300s (5 minutos): equilibrio entre reactividad (un cliente con
    pago PENDING no quiere esperar mucho) y carga sobre la pasarela
    (no la golpeamos cada 10s con todos los pendientes).

    El sleep va antes del trabajo: la primera reconciliacion ocurre 5min
    despues del startup para no competir con la inicializacion de la BD.
    """
    logger.info("Reconciler async iniciado (cada %ds).", interval_seconds)
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            reconcile_once()
        except asyncio.CancelledError:
            # Shutdown limpio: re-lanzamos para que el await del lifespan complete.
            logger.info("Reconciler detenido.")
            raise
        except Exception as exc:  # noqa: BLE001
            # Errores no esperados: logueamos pero NO rompemos el loop.
            logger.exception("Reconciler loop error: %s", exc)
