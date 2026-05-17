"""Auth & Users Service - SSO con JWT (esqueleto Bloque 1).

Responsabilidades del servicio:
- Registro y login de clientes y administradores.
- Emision y refresh de JWT.
- Validacion local del token por parte de los demas microservicios (clave compartida).
- AccessLog: bitacora de inicios de sesion.

En el Bloque 1 solo se exponen /health y /. La logica de negocio se implementa
en el Bloque 2.
"""
from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(
    title=f"Tienda Digital - {settings.service_name}",
    description="Servicio de autenticacion, usuarios, roles y emision de JWT.",
    version="0.1.0",
)


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": settings.service_name,
        "version": app.version,
        "status": "scaffold",
    }


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Healthcheck usado por Docker, Nginx y monitoreo."""
    return {"status": "ok", "service": settings.service_name}
