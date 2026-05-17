"""Inventory-service - esqueleto Bloque 1."""
from fastapi import FastAPI
from app.core.config import settings

app = FastAPI(
    title=f"Tienda Digital - {settings.service_name}",
    version="0.1.0",
)


@app.get("/", tags=["meta"])
def root() -> dict:
    return {"service": settings.service_name, "version": app.version, "status": "scaffold"}


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "service": settings.service_name}
