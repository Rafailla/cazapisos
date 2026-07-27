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


def send_new_listings_email(recipients: list[str], excel_path: str, count_new: int) -> None:
    if not recipients:
        return

    _send(
        recipients,
        subject=f"cazapisos: {count_new} pisos nuevos",
        body=f"Se han encontrado {count_new} piso(s) nuevo(s) que cumplen tus filtros. "
        "Adjunto el Excel con todas las viviendas disponibles.",
        attachment_path=excel_path,
    )


def send_platform_health_digest_email(stale: list[dict]) -> None:
    """Un solo email resumen (nunca uno por plataforma) a los recipients
    tipo system_alerts — los de new_listings nunca lo reciben, ver
    get_active_recipients."""
    recipients = [r["email"] for r in db.get_active_recipients("system_alerts")]
    if not recipients:
        return

    lineas = [f"- {p['name']}: {p['days_without_new']} días sin anuncios nuevos" for p in stale]
    body = (
        f"{len(stale)} plataforma(s) llevan tiempo sin aportar ningún anuncio nuevo. "
        "Puede que hayan cambiado de HTML y el scraper haya dejado de funcionar. "
        "Conviene revisarlas:\n\n" + "\n".join(lineas)
    )

    _send(
        recipients,
        subject=f"cazapisos: informe de plataformas — {len(stale)} posible(s) fallo(s)",
        body=body,
    )
