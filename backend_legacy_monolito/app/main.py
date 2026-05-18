import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import admin_catalog, admin_finance, auth, cart, catalog, health, orders, settings_reviews
from app.core.config import get_settings
from app.utils.observability import response_time_middleware
from app.utils.security_headers import security_headers_middleware


settings = get_settings()

app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(response_time_middleware)
app.middleware("http")(security_headers_middleware)

app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(admin_catalog.router)
app.include_router(admin_finance.router)
app.include_router(settings_reviews.router)
app.include_router(health.router)

_uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(_uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_uploads_dir), name="uploads")
