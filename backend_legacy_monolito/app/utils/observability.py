"""Middleware de observabilidad basica para el monolito legacy.

Mide cada request, expone el tiempo en cabecera HTTP y registra eventos de
request_completed en SystemLog para tener trazabilidad minima en el MVP.
"""
import time
from typing import Callable

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.services.audit_service import add_system_log


async def response_time_middleware(request: Request, call_next: Callable) -> Response:
    """Agrega X-Response-Time-ms y registra la request salvo health checks."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Response-Time-ms"] = str(duration_ms)
    if request.url.path != "/health":
        db: Session = SessionLocal()
        try:
            add_system_log(
                db,
                level="INFO",
                message="request_completed",
                context={
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            db.commit()
        finally:
            db.close()
    return response
