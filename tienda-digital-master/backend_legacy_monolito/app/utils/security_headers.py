"""Middleware de cabeceras de seguridad del monolito legacy."""
from typing import Callable

from fastapi import Request, Response


async def security_headers_middleware(request: Request, call_next: Callable) -> Response:
    """Aplica headers defensivos comunes a todas las respuestas HTTP."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
