"""Envío de emails por SMTP (Gmail). Solo librería estándar."""
import os
import smtplib
from email.message import EmailMessage

import config
import db

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _send(to_addrs: list[str], subject: str, body: str, attachment_path: str | None = None) -> None:
    config.validate_gmail()

    message = EmailMessage()
    message["From"] = config.GMAIL_ADDRESS
    message["To"] = ", ".join(to_addrs)
    message["Subject"] = subject
    message.set_content(body)

    if attachment_path:
        with open(attachment_path, "rb") as f:
            message.add_attachment(
                f.read(),
                maintype="application",
                subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=os.path.basename(attachment_path),
            )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        smtp.send_message(message)


def send_new_listings_email(excel_path: str, count_new: int) -> None:
    recipients = [r["email"] for r in db.get_active_recipients("new_listings")]
    if not recipients:
        return

    _send(
        recipients,
        subject=f"cazapisos: {count_new} pisos nuevos",
        body=f"Se han encontrado {count_new} piso(s) nuevo(s) que cumplen tus filtros. "
        "Adjunto el Excel con todas las viviendas disponibles.",
        attachment_path=excel_path,
    )


def send_platform_alert_email(platform_name: str, days_without_new: int) -> None:
    recipients = [r["email"] for r in db.get_active_recipients("system_alerts")]
    if not recipients:
        return

    _send(
        recipients,
        subject=f"cazapisos: posible fallo en {platform_name}",
        body=f"{platform_name} lleva {days_without_new} días sin aportar ningún anuncio nuevo. "
        "Puede que la plataforma haya cambiado de HTML y el scraper haya dejado de funcionar.",
    )
