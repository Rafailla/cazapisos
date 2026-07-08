"""Genera el Excel de viviendas disponibles adjunto al email de novedades."""
import os
import tempfile
from datetime import datetime

from openpyxl import Workbook

COLUMNS = [
    "Tipo",
    "Municipio",
    "Precio",
    "m2",
    "Habitaciones",
    "Baños",
    "Plataforma/vendedor",
    "Enlace",
    "Disponible",
    "Última comprobación",
]


def build_listings_excel(listings: list[dict]) -> str:
    ordenados = sorted(listings, key=lambda l: l.get("first_seen_at") or "", reverse=True)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "VIVIENDAS"
    sheet.append(COLUMNS)

    for listing in ordenados:
        plataforma_vendedor = listing.get("platform_name") or ""
        if listing.get("seller"):
            plataforma_vendedor = f"{plataforma_vendedor} ({listing['seller']})".strip()

        sheet.append(
            [
                listing.get("property_type"),
                listing.get("municipality"),
                listing.get("price"),
                listing.get("m2"),
                listing.get("bedrooms"),
                listing.get("bathrooms"),
                plataforma_vendedor,
                listing.get("url"),
                "Sí" if listing.get("available") else "No",
                listing.get("last_seen_available_at"),
            ]
        )

    fd, path = tempfile.mkstemp(
        prefix=f"cazapisos_viviendas_{datetime.now().strftime('%Y%m%d_%H%M%S')}_",
        suffix=".xlsx",
    )
    os.close(fd)
    workbook.save(path)
    return path
