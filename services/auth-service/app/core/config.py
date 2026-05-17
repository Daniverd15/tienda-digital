"""Configuracion por variable de entorno (Pydantic Settings)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "auth-service"
    service_port: int = 8001
    database_url: str = (
        "mysql+pymysql://auth_user:auth_pass@mysql:3306/auth_db?charset=utf8mb4"
    )
    jwt_secret: str = "cambiar_en_produccion_pero_compartido_entre_servicios"
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 7
    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    smtp_from: str = "no-reply@tiendadigital.local"


settings = Settings()
