"""Configuracion central del monolito legacy.

Lee variables de entorno/.env mediante Pydantic Settings y expone un singleton
cacheado para que FastAPI, SQLAlchemy y seguridad compartan los mismos valores
de conexion, CORS y JWT.
"""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Contrato de variables configurables del backend legacy."""
    app_name: str = "Tienda Digital Scrum"
    environment: str = "local"
    database_url: str = "mysql+pymysql://tienda_user:tienda_password@localhost:3306/tienda_digital"
    jwt_secret_key: str = Field(default="change-me-in-production")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_sql: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> List[str]:
        """Convierte la cadena CSV de CORS en la lista requerida por FastAPI."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuracion cacheada para evitar releer el entorno."""
    return Settings()
