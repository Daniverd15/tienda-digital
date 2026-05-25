"""Envio directo de correos a Mailhog via SMTP.

Auth maneja su propio correo de bienvenida sin pasar por Commerce (cohesion
por dominio). Si el SMTP no esta disponible, se loguea y se sigue: el correo
no es bloqueante para el registro.
"""
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> bool:
    """Envia un correo simple por SMTP y falla de forma no bloqueante."""
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as s:
            s.send_message(msg)
        logger.info("Correo enviado a %s asunto=%s", to, subject)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo enviar correo a %s: %s", to, exc)
        return False


def send_welcome_email(name: str, email: str) -> bool:
    """Construye y envia el correo de bienvenida del registro."""
    body = (
        f"Hola {name},\n\n"
        "Tu cuenta en Tienda Digital fue creada con exito.\n"
        "Ya puedes explorar el catalogo, agregar productos al carrito y comprar.\n\n"
        "Si no fuiste tu quien creo esta cuenta, ignora este mensaje.\n"
    )
    return send_email(email, "Bienvenido(a) a Tienda Digital", body)
