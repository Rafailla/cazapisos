"""Envío de emails por SMTP (Gmail). Solo librería estándar."""
import html
import os
import smtplib
from email.message import EmailMessage

import config
import db

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# Autodetección de columnas opcionales de listings (paso 0, sesión 2026-07-27):
# hoy NINGUNA existe en el esquema real (comprobado contra Supabase), pero el
# HTML del email no debe asumirlo — si en el futuro se añade alguna con
# cualquiera de estos nombres, se usa sola sin tocar este código.
_TITLE_KEYS = ("title", "titulo", "título", "nombre", "name")
_IMAGE_KEYS = ("image_url", "imagen", "foto", "main_image", "thumbnail", "photo", "picture")


def _send(
    to_addrs: list[str],
    subject: str,
    body: str,
    html_body: str | None = None,
    attachment_path: str | None = None,
) -> None:
    config.validate_gmail()

    message = EmailMessage()
    message["From"] = config.GMAIL_ADDRESS
    message["To"] = ", ".join(to_addrs)
    message["Subject"] = subject
    message.set_content(body)
    if html_body:
        # add_alternative() convierte el mensaje en multipart/alternative
        # (texto + html); si luego se llama add_attachment(), EmailMessage
        # lo envuelve todo en multipart/mixed automáticamente — no hace
        # falta construir MIMEMultipart a mano.
        message.add_alternative(html_body, subtype="html")

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


def _first_present(listing: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = listing.get(key)
        if value:
            return str(value)
    return None


def _fmt_price(price) -> str | None:
    if price is None:
        return None
    return f"{price:,.0f} €".replace(",", ".")


def _fmt_m2(m2) -> str | None:
    if m2 is None:
        return None
    m2 = float(m2)
    return f"{int(m2) if m2.is_integer() else m2} m²"


def _listing_title(listing: dict) -> str:
    titulo = _first_present(listing, _TITLE_KEYS)
    if titulo:
        return titulo
    partes = [listing.get("property_type"), listing.get("municipality")]
    base = " en ".join(p for p in partes if p) or "Piso"
    precio = _fmt_price(listing.get("price"))
    return f"{base} — {precio}" if precio else base


def _render_listing_html(listing: dict) -> str:
    titulo = html.escape(_listing_title(listing))

    imagen_url = _first_present(listing, _IMAGE_KEYS)
    imagen_html = ""
    if imagen_url:
        imagen_html = (
            f'<img src="{html.escape(imagen_url)}" alt="{titulo}" '
            'style="max-width:480px;width:100%;height:auto;border-radius:6px;'
            'display:block;margin:8px 0;">'
        )

    plataforma_vendedor = listing.get("platform_name") or ""
    if listing.get("seller"):
        plataforma_vendedor = f"{plataforma_vendedor} ({listing['seller']})".strip()

    datos = [
        ("Precio", _fmt_price(listing.get("price"))),
        ("Superficie", _fmt_m2(listing.get("m2"))),
        ("Habitaciones", listing.get("bedrooms")),
        ("Baños", listing.get("bathrooms")),
        ("Tipo", listing.get("property_type")),
        ("Municipio", listing.get("municipality")),
        ("Plataforma/vendedor", plataforma_vendedor or None),
        ("Disponible", "Sí" if listing.get("available") else None),
    ]
    filas = "".join(
        f'<tr><td style="padding:4px 12px 4px 0;color:#666;font-family:Arial,sans-serif;'
        f'font-size:14px;">{html.escape(etiqueta)}</td>'
        f'<td style="padding:4px 0;font-weight:bold;font-family:Arial,sans-serif;'
        f'font-size:14px;">{html.escape(str(valor))}</td></tr>'
        for etiqueta, valor in datos
        if valor not in (None, "")
    )
    tabla_html = f'<table style="border-collapse:collapse;">{filas}</table>' if filas else ""

    url = listing.get("url")
    enlace_html = ""
    if url:
        enlace_html = (
            f'<p style="margin:8px 0;"><a href="{html.escape(url)}" '
            'style="color:#1a73e8;font-weight:bold;text-decoration:none;'
            'font-family:Arial,sans-serif;font-size:14px;">Ver anuncio →</a></p>'
        )

    return (
        '<hr style="border:none;border-top:1px solid #ddd;margin:16px 0;">'
        f'<h2 style="font-size:16px;margin:0 0 8px;font-family:Arial,sans-serif;">{titulo}</h2>'
        f"{imagen_html}{tabla_html}{enlace_html}"
    )


def build_new_listings_html(new_listings: list[dict], total_new: int) -> str:
    """HTML con estilos inline (nada de <style>, los clientes de correo lo
    quitan) con el resumen de los pisos nuevos de esta ejecución — mismos
    datos que el Excel adjunto, pero legible y con enlace clicable. Limita a
    email_max_listings_in_body (app_settings, default 25) para no generar un
    correo gigante; el resto queda solo en el Excel."""
    max_listings = int(db.get_app_setting("email_max_listings_in_body", "25"))
    listado = new_listings[:max_listings]

    bloques = "".join(_render_listing_html(listing) for listing in listado)

    resto = total_new - len(listado)
    nota_resto = (
        f'<p style="font-family:Arial,sans-serif;font-size:14px;color:#555;">'
        f"y {resto} más en el Excel adjunto.</p>"
        if resto > 0
        else ""
    )

    return (
        '<div style="font-family:Arial,sans-serif;">'
        f'<h1 style="font-size:20px;">{total_new} piso(s) nuevo(s) encontrados</h1>'
        f"{bloques}{nota_resto}"
        "</div>"
    )


def send_new_listings_email(
    recipients: list[str],
    excel_path: str,
    count_new: int,
    new_listings: list[dict] | None = None,
) -> None:
    if not recipients:
        return

    # Si no se pasan los dicts de los pisos nuevos (o viene vacío), cae al
    # cuerpo de texto plano de siempre — compatible hacia atrás.
    html_body = build_new_listings_html(new_listings, count_new) if new_listings else None

    _send(
        recipients,
        subject=f"cazapisos: {count_new} pisos nuevos",
        body=f"Se han encontrado {count_new} piso(s) nuevo(s) que cumplen tus filtros. "
        "Adjunto el Excel con todas las viviendas disponibles.",
        html_body=html_body,
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
