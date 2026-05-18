"""SMTP a Mailhog para correos transaccionales (no bloqueante)."""
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> bool:
    if not to:
        return False
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as s:
            s.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo enviar correo a %s: %s", to, exc)
        return False
