"""Auth & Users Service.

Bounded context: identidad (usuarios, roles, tokens) y bitacora de accesos.

Patrones materializados aqui:
- SSO con JWT (emision y validacion compartida con los demas servicios via JWT_SECRET).
- Health Check (/health) que verifica conexion a MySQL.
- Correlation ID propagado en los logs de acceso.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import get_password_hash
from app.models import User

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("auth-service")


def ensure_seed_admin() -> None:
    """Crea un admin por defecto si la BD esta vacia. Solo en local."""
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return
        admin = User(
            name="Administrador Tienda",
            email="admin@tienda.com",
            phone="3000000000",
            password_hash=get_password_hash("Admin1234*"),
            role="admin",
            active=True,
        )
        db.add(admin)
        db.commit()
        logger.info("Admin seed creado: admin@tienda.com / Admin1234*")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando %s ...", settings.service_name)
    Base.metadata.create_all(bind=engine)
    ensure_seed_admin()
    logger.info("%s listo en puerto %s", settings.service_name, settings.service_port)
    yield


app = FastAPI(
    title="Tienda Digital - Auth & Users",
    description="Servicio de autenticacion, usuarios, roles y emision de JWT.",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,  # evita 307 que rompen el proxy del gateway
)

# CORS permisivo en desarrollo; el gateway hace lo principal en produccion
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
    """Healthcheck profundo: valida MySQL."""
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # noqa: BLE001
        logger.error("Healthcheck fallo MySQL: %s", exc)
    finally:
        try:
            db.close()
        except Exception:  # noqa: BLE001
            pass
    status = "ok" if db_ok else "degraded"
    return {"status": status, "service": settings.service_name, "checks": {"mysql": db_ok}}


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(admin_router)
