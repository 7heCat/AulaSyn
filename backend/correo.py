"""Envío de correos por SMTP (HU4). Variables en .env:
SMTP_HOST, SMTP_PORT (587), SMTP_USUARIO, SMTP_CLAVE, SMTP_REMITENTE (opcional)."""

import logging
import os
import smtplib
import threading
from email.message import EmailMessage

log = logging.getLogger(__name__)


def smtp_configurado():
    return all(os.getenv(v) for v in ("SMTP_HOST", "SMTP_USUARIO", "SMTP_CLAVE"))


def _enviar(destino, asunto, texto):
    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = os.getenv("SMTP_REMITENTE") or os.getenv("SMTP_USUARIO")
    msg["To"] = destino
    msg.set_content(texto)
    try:
        with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", "587")), timeout=15) as s:
            s.starttls()
            s.login(os.getenv("SMTP_USUARIO"), os.getenv("SMTP_CLAVE"))
            s.send_message(msg)
    except Exception:
        log.exception("No se pudo enviar el correo")


def enviar_en_segundo_plano(destino, asunto, texto):
    """No bloquea la respuesta (así el tiempo no revela si el correo existe)."""
    threading.Thread(target=_enviar, args=(destino, asunto, texto), daemon=True).start()


def enviar_codigo_recuperacion(destino, nombres, codigo, minutos, debug=False):
    if not smtp_configurado():
        if debug:  # solo en desarrollo: el código aparece en la consola de Flask
            log.warning("SMTP sin configurar. Código de %s: %s", destino, codigo)
        else:
            log.error("SMTP sin configurar: no se envió el código de recuperación")
        return
    enviar_en_segundo_plano(
        destino,
        "AulaSyn · Código para recuperar tu contraseña",
        f"Hola {nombres},\n\nTu código de verificación es: {codigo}\n\n"
        f"Vence en {minutos} minutos y solo se puede usar una vez.\n"
        "Si no lo solicitaste, ignora este mensaje.\n\nAulaSyn"
    )
