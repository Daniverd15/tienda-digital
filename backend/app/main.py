from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin_catalog, admin_finance, auth, cart, catalog, orders
from app.core.config import get_settings


settings = get_settings()

app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(admin_catalog.router)
app.include_router(admin_finance.router)
