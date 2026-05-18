"""Commerce Service.

Bounded context: carrito, checkout, pedidos, estados logisticos, resenas,
notificaciones, empleados, gastos, finanzas y bitacora administrativa.

Orquestador de la SAGA orquestada sincrona del checkout (Nivel 1 del alcance,
informe Fase 1 seccion 11.0):
  Commerce -> Inventory.reserve -> Payment.charge ->
              Inventory.confirm (si APPROVED) | Inventory.release (si REJECTED)
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.admin import router as admin_router
from app.api.cart import router as cart_router
from app.api.checkout import router as checkout_router
from app.api.notifications import router as notifications_router
from app.api.orders import router as orders_router
from app.api.reviews import router as reviews_router
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("commerce-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando %s ...", settings.service_name)
    Base.metadata.create_all(bind=engine)
    logger.info("%s listo en puerto %s", settings.service_name, settings.service_port)
    yield


app = FastAPI(
    title="Tienda Digital - Commerce",
    description="Carrito, checkout (SAGA), pedidos, estados, resenas, notificaciones, finanzas.",
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


app.include_router(cart_router)
app.include_router(checkout_router)
app.include_router(orders_router)
app.include_router(reviews_router)
app.include_router(notifications_router)
app.include_router(admin_router)
