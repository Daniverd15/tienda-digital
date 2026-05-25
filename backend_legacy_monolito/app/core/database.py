"""Conexion SQLAlchemy del monolito legacy.

Define engine, session factory y Base declarativa usados por todas las rutas.
El pool_pre_ping evita conexiones MySQL stale en desarrollo con Docker, y
get_db entrega una sesion por request para que FastAPI cierre recursos al
terminar cada operacion.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings


settings = get_settings()

engine = create_engine(
    settings.database_url,
    echo=settings.log_sql,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency de FastAPI: abre una sesion y la cierra al finalizar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
