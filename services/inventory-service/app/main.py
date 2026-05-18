"""Inventory Service.

Bounded context: variantes (SKU), stock, reservas y movimientos.
Fuente unica de verdad del inventario.

Patrones materializados:
- Lock distribuido con Redis (SET NX EX) por variante.
- SELECT FOR UPDATE en MySQL para consistencia transaccional.
- Reservas con expiracion (scheduler async cada 60s).
- Health Check profundo (MySQL + Redis).
- SSO con JWT validado localmente.
- Comunicacion REST con Catalog para validar product_id.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.admin import router as admin_router
from app.api.internal import router as internal_router
from app.api.public import router as public_router
from app.core import redis_lock
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.models import ProductVariant
from app.services.scheduler import run_scheduler_forever

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("inventory-service")


def ensure_seed() -> None:
    """Crea variantes para los productos del seed de Catalog (ids 1..5)."""
    db = SessionLocal()
    try:
        if db.query(ProductVariant).count() > 0:
            return
        variantes = [
            # Camiseta negra
            dict(product_id=1, sku="CAM-NEG-S", color="negro",  size="S",  cost=22000, price=49000, stock=10),
            dict(product_id=1, sku="CAM-NEG-M", color="negro",  size="M",  cost=22000, price=49000, stock=15),
            dict(product_id=1, sku="CAM-NEG-L", color="negro",  size="L",  cost=22000, price=49000, stock=8),
            # Camiseta blanca
            dict(product_id=2, sku="CAM-BLA-M", color="blanco", size="M",  cost=22000, price=49000, stock=12),
            dict(product_id=2, sku="CAM-BLA-L", color="blanco", size="L",  cost=22000, price=49000, stock=4),
            # Gorra urbana
            dict(product_id=3, sku="GOR-AZU",   color="azul",   size=None, cost=16000, price=35000, stock=20),
            dict(product_id=3, sku="GOR-NEG",   color="negro",  size=None, cost=16000, price=35000, stock=3),   # alerta
            # Tenis
            dict(product_id=4, sku="TEN-40",    color="blanco", size="40", cost=95000, price=189000, stock=6),
            dict(product_id=4, sku="TEN-42",    color="blanco", size="42", cost=95000, price=189000, stock=6),
            dict(product_id=4, sku="TEN-44",    color="negro",  size="44", cost=95000, price=189000, stock=0),   # sin stock
            # Mochila
            dict(product_id=5, sku="MOC-CLA",   color="negro",  size=None, cost=65000, price=129000, stock=18),
        ]
        for v in variantes:
            db.add(ProductVariant(**v, active=True, reserved_stock=0))
        db.commit()
        logger.info("Seed inventory creado: %d variantes", len(variantes))
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando %s ...", settings.service_name)
    Base.metadata.create_all(bind=engine)
    ensure_seed()
    task = asyncio.create_task(run_scheduler_forever(interval_seconds=60))
    logger.info("%s listo en puerto %s", settings.service_name, settings.service_port)
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Tienda Digital - Inventory",
    description="Fuente unica de verdad del stock; variantes, reservas y movimientos.",
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
    return {"service": settings.service_name, "version": app.version, "status": "ready"}


@app.get("/health", tags=["meta"])
def health() -> dict:
    db_ok = False
    redis_ok = False
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db_ok = True
        db.close()
    except Exception as exc:  # noqa: BLE001
        logger.error("MySQL fail: %s", exc)
    try:
        redis_ok = redis_lock.health()
    except Exception:  # noqa: BLE001
        redis_ok = False
    status_ = "ok" if (db_ok and redis_ok) else "degraded"
    return {
        "status": status_,
        "service": settings.service_name,
        "checks": {"mysql": db_ok, "redis_lock": redis_ok},
    }


app.include_router(public_router)
app.include_router(internal_router)
app.include_router(admin_router)
