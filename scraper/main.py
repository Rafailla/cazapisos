"""Punto de entrada del scraper."""
import os
import sys
from datetime import datetime, timezone

import config
import db
import emailer
import excel_export
import matching
from platforms import servihabitat

DIAS_SIN_NOVEDADES_ALERTA = 5

# Registro de scrapers por nombre de plataforma. Las plataformas activas que no
# tengan `search_url_base` relleno (o que no tengan scraper implementado
# todavía) se saltan con un aviso.
PLATFORM_SCRAPERS = {
    "Servihabitat": servihabitat.fetch_listings,
}


def _provincia_slugs(filters: list[dict]) -> list[str]:
    """Provincias a escrapear: `filters.province_slug` de cada perfil activo.
    `filters.zona` es solo para matching.py (lista de localidades)."""
    return sorted({f["province_slug"] for f in filters if f.get("province_slug")})


def _process_platform(platform: dict, filters: list[dict]) -> tuple[int, int]:
    fetch = PLATFORM_SCRAPERS.get(platform["name"])
    if fetch is None or not platform.get("search_url_base"):
        print(f"saltando {platform['name']}: falta search_url_base")
        return 0, 0

    nuevos = 0
    existentes = 0
    ahora = datetime.now(timezone.utc).isoformat()

    for slug in _provincia_slugs(filters):
        for listing in fetch(slug):
            matched_ids = matching.matches_any_filter(listing, filters)
            if not matched_ids:
                continue

            dedup_hash = listing["external_id"]
            existing = db.find_listing(platform["id"], dedup_hash)

            if existing:
                db.touch_listing(existing["id"], ahora)
                existentes += 1
            else:
                db.insert_listing(
                    {
                        "platform_id": platform["id"],
                        "external_id": listing["external_id"],
                        "dedup_hash": dedup_hash,
                        "url": listing["url"],
                        "price": listing["price"],
                        "bedrooms": listing["bedrooms"],
                        "bathrooms": listing["bathrooms"],
                        "m2": listing["m2"],
                        "property_type": listing["property_type"],
                        "municipality": listing["municipality"],
                        "matched_filter_ids": matched_ids,
                    }
                )
                nuevos += 1

    return nuevos, existentes


def main() -> int:
    trigger_type = os.environ.get("TRIGGER_TYPE", "manual")
    total_nuevos = 0
    status = "success"
    notes = None

    try:
        config.validate()
        plataformas = db.get_active_platforms()
        filtros = db.get_active_filters()
        print(f"{len(plataformas)} plataformas activas, {len(filtros)} perfiles de filtro activos")

        plataformas_con_novedades = []
        for platform in plataformas:
            if platform.get("method") != "scraping":
                continue
            nuevos, existentes = _process_platform(platform, filtros)
            print(f"{platform['name']}: {nuevos} anuncios nuevos, {existentes} ya existentes")
            total_nuevos += nuevos
            if nuevos > 0:
                plataformas_con_novedades.append(platform)

        for platform in plataformas_con_novedades:
            db.update_platform_last_new_listing(platform["id"])

        if total_nuevos > 0:
            listings = db.get_available_listings()
            excel_path = excel_export.build_listings_excel(listings)
            emailer.send_new_listings_email(excel_path, total_nuevos)

        ahora = datetime.now(timezone.utc)
        for stale in db.get_stale_platforms(DIAS_SIN_NOVEDADES_ALERTA):
            referencia = stale.get("last_new_listing_at") or stale.get("created_at")
            dias = (ahora - datetime.fromisoformat(referencia)).days
            emailer.send_platform_alert_email(stale["name"], dias)

    except Exception as exc:
        status = "error"
        notes = str(exc)
        print(f"Error: {exc}", file=sys.stderr)

    try:
        db.log_execution(trigger_type, total_nuevos, status, notes)
    except Exception as exc:
        print(f"No se pudo registrar execution_log: {exc}", file=sys.stderr)

    return 0 if status == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
