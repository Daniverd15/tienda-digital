"""Payment Service.

Bounded context: pagos contra pasarela mock, intentos y reembolsos.

Bloque 5: version basica funcional para que Commerce pueda completar el
checkout end-to-end (POST /payments contra mock).
Bloque 6 (proximo): se le agrega Circuit Breaker basado en Redis,
reintentos con backoff exponencial y endpoint de conciliacion.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.payments import router as payments_router
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.services.gateway_client import provider_cb
from app.services.reconciler import run_reconciler_forever

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("payment-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa tablas y worker periodico de reconciliacion."""
    logger.info("Inicializando %s ...", settings.service_name)
    Base.metadata.create_all(bind=engine)
    # Worker async: cada 5 min reconcilia PENDING/FAILED
    task = asyncio.create_task(run_reconciler_forever(interval_seconds=300))
    logger.info("%s listo en puerto %s (CB %s)",
                settings.service_name, settings.service_port, provider_cb.get_state().value)
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Tienda Digital - Payment",
    description="Pagos contra pasarela externa (mock).",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["meta"])
def root() -> dict:
    """Metadata liviana para discovery y pruebas manuales."""
    return {"service": settings.service_name, "version": app.version, "status": "ready"}


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Healthcheck profundo: valida MySQL."""
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db_ok = True
        db.close()
    except Exception as exc:  # noqa: BLE001
        logger.error("MySQL fail: %s", exc)
    return {
        "status": "ok" if db_ok else "degraded",
        "service": settings.service_name,
        "checks": {"mysql": db_ok},
    }


app.include_router(payments_router)
