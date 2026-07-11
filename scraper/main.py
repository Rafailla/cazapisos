"""Punto de entrada del scraper."""
import os
import sys
from datetime import datetime, timezone

import config
import db
import emailer
import excel_export
import matching
from platforms import aliseda, pisos, servihabitat, solvia

DIAS_SIN_NOVEDADES_ALERTA = 5

# Registro de scrapers por nombre de plataforma. Las plataformas activas que no
# tengan `search_url_base` relleno (o que no tengan scraper implementado
# todavía) se saltan con un aviso.
PLATFORM_SCRAPERS = {
    "Servihabitat": servihabitat.fetch_listings,
    "Pisos.com": pisos.fetch_listings,
    "Solvia": solvia.fetch_listings,
    "Aliseda": aliseda.fetch_listings,
}

# fetch_tagged_ids(province_slug, tag) por plataforma, misma firma en las dos:
# devuelve un conjunto de external_id (vacío si esa plataforma no tiene un
# filtro URL real para ese tag concreto — ver cada módulo de plataforma).
PLATFORM_TAG_FETCHERS = {
    "Servihabitat": servihabitat.fetch_tagged_ids,
    "Pisos.com": pisos.fetch_tagged_ids,
    "Solvia": solvia.fetch_tagged_ids,
    "Aliseda": aliseda.fetch_tagged_ids,
}


def _provincia_slugs(filters: list[dict]) -> list[str]:
    """Provincias a escrapear: `filters.province_slug` de cada perfil activo.
    `filters.zona` es solo para matching.py (lista de localidades)."""
    return sorted({f["province_slug"] for f in filters if f.get("province_slug")})


def _process_platform(platform: dict, filters: list[dict]) -> tuple[int, int, bool, list[list[str]]]:
    """Devuelve (nuevos, existentes, revisado, nuevos_matched_filter_ids).
    `revisado` es False cuando la plataforma se salta por falta de
    scraper/search_url_base — en ese caso no se debe marcar como comprobada
    (last_checked_at). `nuevos_matched_filter_ids` trae, por cada anuncio
    NUEVO insertado en esta llamada, la lista de filter_id que matcheó — se
    usa luego para saber cuántos anuncios nuevos le tocan a cada grupo en el
    email (ver _count_new_for_group en main())."""
    fetch = PLATFORM_SCRAPERS.get(platform["name"])
    if fetch is None or not platform.get("search_url_base"):
        print(f"saltando {platform['name']}: falta search_url_base")
        return 0, 0, False, []

    nuevos = 0
    existentes = 0
    nuevos_matched_filter_ids: list[list[str]] = []
    ahora = datetime.now(timezone.utc).isoformat()

    tag_fetch = PLATFORM_TAG_FETCHERS.get(platform["name"])

    for slug in _provincia_slugs(filters):
        # Piscina/condición se resuelven cruzando el external_id contra las
        # URLs por característica en vez de visitar la ficha de cada anuncio.
        # Una llamada por tag y por provincia, no por anuncio. Si la
        # plataforma no tiene un filtro URL real para un tag concreto, su
        # fetch_tagged_ids devuelve un conjunto vacío (no falla).
        pool_ids: set[str] = set()
        nueva_ids: set[str] = set()
        segunda_mano_ids: set[str] = set()
        if tag_fetch:
            pool_ids = tag_fetch(slug, "piscina")
            nueva_ids = tag_fetch(slug, "aestrenar")
            segunda_mano_ids = tag_fetch(slug, "segundamano")

        for listing in fetch(slug):
            external_id = listing["external_id"]
            # Igual que con condition: si la plataforma ya resuelve piscina
            # ella misma (ver solvia.py, que no necesita cruzar tags porque
            # el dato viene directo en cada anuncio) se respeta ese valor en
            # vez de forzarlo a False por no aparecer en pool_ids.
            has_pool = external_id in pool_ids or bool(listing.get("has_pool"))
            if external_id in nueva_ids:
                condition = "nueva"
            elif external_id in segunda_mano_ids:
                condition = "segunda_mano"
            else:
                # Si la propia plataforma ya conoce la condición sin
                # necesidad de cruzar tags (ej. Pisos.com, ver pisos.py), se
                # respeta ese valor en vez de forzar null.
                condition = listing.get("condition")
            listing["has_pool"] = has_pool
            listing["condition"] = condition

            matched_ids = matching.matches_any_filter(listing, filters)
            if not matched_ids:
                continue

            dedup_hash = external_id
            existing = db.find_listing(platform["id"], dedup_hash)

            if existing:
                db.touch_listing(existing["id"], ahora, has_pool, condition)
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
                        "has_pool": has_pool,
                        "condition": condition,
                    }
                )
                nuevos += 1
                nuevos_matched_filter_ids.append(matched_ids)

    return nuevos, existentes, True, nuevos_matched_filter_ids


def _filter_ids_for_group(filters: list[dict], group_id: str) -> set[str]:
    return {f["id"] for f in filters if f.get("group_id") == group_id}


def _listings_for_group(listings: list[dict], filter_ids_grupo: set[str]) -> list[dict]:
    """listings.matched_filter_ids ya viene calculado (en insert_listing, ver
    _process_platform) contra TODOS los filtros activos de TODOS los grupos
    — aquí solo se cruza con los filter_id de un grupo concreto para saber
    qué le corresponde a ese grupo en el Excel/email."""
    return [
        listing
        for listing in listings
        if filter_ids_grupo & set(listing.get("matched_filter_ids") or [])
    ]


def _count_new_for_group(nuevos_matched_filter_ids: list[list[str]], filter_ids_grupo: set[str]) -> int:
    return sum(1 for matched in nuevos_matched_filter_ids if filter_ids_grupo & set(matched))


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
        todos_nuevos_matched_filter_ids: list[list[str]] = []
        for platform in plataformas:
            if platform.get("method") != "scraping":
                continue
            nuevos, existentes, revisado, nuevos_matched_filter_ids = _process_platform(platform, filtros)
            print(f"{platform['name']}: {nuevos} anuncios nuevos, {existentes} ya existentes")
            total_nuevos += nuevos
            todos_nuevos_matched_filter_ids.extend(nuevos_matched_filter_ids)
            if revisado:
                db.update_platform_check_result(platform["id"], nuevos)
            if nuevos > 0:
                plataformas_con_novedades.append(platform)

        for platform in plataformas_con_novedades:
            db.update_platform_last_new_listing(platform["id"])

        if total_nuevos > 0:
            listings = db.get_available_listings()
            # Un email por grupo, no uno global: cada grupo (amigos, padres,
            # ...) solo ve sus propios filtros/anuncios/destinatarios, nunca
            # los de otro grupo. Un grupo sin anuncios que le encajen esta
            # vez simplemente no recibe email.
            for grupo in db.get_groups():
                filter_ids_grupo = _filter_ids_for_group(filtros, grupo["id"])
                if not filter_ids_grupo:
                    continue

                listings_grupo = _listings_for_group(listings, filter_ids_grupo)
                if not listings_grupo:
                    continue

                count_nuevos_grupo = _count_new_for_group(todos_nuevos_matched_filter_ids, filter_ids_grupo)
                recipients = [
                    r["email"] for r in db.get_active_recipients_by_group(grupo["id"], "new_listings")
                ]
                excel_path = excel_export.build_listings_excel(listings_grupo)
                emailer.send_new_listings_email(recipients, excel_path, count_nuevos_grupo)

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
