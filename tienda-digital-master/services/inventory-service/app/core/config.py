"""Configuracion por variable de entorno."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables de entorno que parametrizan Inventory Service."""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "inventory-service"
    service_port: int = 8003
    database_url: str = "mysql+pymysql://inventory_user:inventory_pass@mysql:3306/inventory_db?charset=utf8mb4"
    jwt_secret: str = "cambiar_en_produccion_pero_compartido_entre_servicios"
    jwt_algorithm: str = "HS256"
    redis_url: str = "redis://redis:6379/0"


settings = Settings()
