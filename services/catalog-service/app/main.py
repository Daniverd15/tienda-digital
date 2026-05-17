"""Catalog Service.

Bounded context: productos, categorias, imagenes, configuracion de tienda,
mensajes informativos y rating cacheado.

Patrones materializados:
- Cache-Aside con Redis (TTL + invalidacion en /admin/*).
- Health Check (/health) que valida MySQL y Redis.
- SSO con JWT validado localmente (no consulta auth_db).
- Comunicacion REST a Inventory para enriquecer detalle con variantes/stock.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.admin import router as admin_router
from app.api.public import router as public_router
from app.core import cache
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.models import (
    Category,
    InformativeMessage,
    Product,
    RatingSummary,
    StoreSetting,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("catalog-service")


def ensure_seed() -> None:
    """Crea categorias, productos y settings minimos para demo si la BD esta vacia."""
    db = SessionLocal()
    try:
        if db.query(Category).count() > 0:
            return

        s = StoreSetting(
            commercial_name="Distrito Urbano",
            logo_url="https://images.unsplash.com/photo-1503602642458-232111445657?w=240&q=80",
            primary_color="#1f7a5c",
            secondary_color="#f4b942",
            banner_url="https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=1600&q=80",
            contact_email="contacto@distritourbano.com",
            contact_phone="+57 3000000000",
            currency="COP",
            stock_threshold=5,
        )
        db.add(s)

        db.add(InformativeMessage(
            title="Envio gratis sobre $200.000",
            content="Aplica para compras superiores a $200.000 en todo el catalogo.",
            type="info",
            active=True,
        ))
        db.add(InformativeMessage(
            title="Politica de devoluciones 15 dias",
            content="Tienes 15 dias calendario para cambios y devoluciones.",
            type="info",
            active=True,
        ))

        ropa = Category(name="Ropa", description="Camisetas, pantalones y mas", active=True)
        accesorios = Category(name="Accesorios", description="Gorras, cinturones, mochilas", active=True)
        calzado = Category(name="Calzado", description="Tenis y zapatillas", active=True)
        db.add_all([ropa, accesorios, calzado])
        db.flush()

        productos = [
            Product(
                category_id=ropa.id, name="Camiseta basica negra",
                description="Camiseta basica 100% algodon.",
                long_description="Tela suave de 180 gr/m2. Disponible en varias tallas.",
                base_price=49000, published=True,
                image_url="https://images.unsplash.com/photo-1576566588028-4147f3842f27?w=400&q=80",
            ),
            Product(
                category_id=ropa.id, name="Camiseta basica blanca",
                description="Camiseta basica 100% algodon, blanca.",
                long_description="Misma tela que la negra. Tallas S a XL.",
                base_price=49000, published=True,
                image_url="https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400&q=80",
            ),
            Product(
                category_id=accesorios.id, name="Gorra urbana",
                description="Gorra urbana ajustable.",
                long_description="Material poliester, cierre con velcro.",
                base_price=35000, published=True,
                image_url="https://images.unsplash.com/photo-1521369909029-2afed882baee?w=400&q=80",
            ),
            Product(
                category_id=calzado.id, name="Tenis deportivos",
                description="Tenis para uso diario y entrenamiento ligero.",
                long_description="Suela de goma, plantilla de espuma, tallas 38-44.",
                base_price=189000, published=True,
                image_url="https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=400&q=80",
            ),
            Product(
                category_id=accesorios.id, name="Mochila clasica",
                description="Mochila resistente al agua con bolsillo para laptop.",
                long_description="Capacidad 22L, compartimento acolchado para portatil 15''.",
                base_price=129000, published=True,
                image_url="https://images.unsplash.com/photo-1622560480605-d83c853bc5c3?w=400&q=80",
            ),
        ]
        for p in productos:
            db.add(p)
        db.flush()
        for p in productos:
            db.add(RatingSummary(product_id=p.id, average=0.0, count=0))
        db.commit()
        logger.info("Seed catalog creado: 3 categorias, %d productos", len(productos))
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando %s ...", settings.service_name)
    Base.metadata.create_all(bind=engine)
    ensure_seed()
    logger.info("%s listo en puerto %s", settings.service_name, settings.service_port)
    yield


app = FastAPI(
    title="Tienda Digital - Catalog",
    description="Servicio de catalogo, categorias, productos, settings y mensajes.",
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
        redis_ok = cache.health()
    except Exception:  # noqa: BLE001
        redis_ok = False
    status_ = "ok" if (db_ok and redis_ok) else "degraded"
    return {
        "status": status_,
        "service": settings.service_name,
        "checks": {"mysql": db_ok, "redis": redis_ok},
    }


app.include_router(public_router)
app.include_router(admin_router)
