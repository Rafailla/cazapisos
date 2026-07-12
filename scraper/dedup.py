"""Detecta posibles duplicados del mismo inmueble anunciado en más de una
plataforma (sesión 2026-07-11). Solo MARCA (listings.possible_duplicate +
listings.duplicate_group_id) — nunca fusiona ni descarta ningún anuncio, la
decisión final la toma quien vea el Excel (el amigo o los padres).

Criterio (mismo margen que app_settings define, no hardcodeado):
- precio: dentro de ±dedup_price_margin_pct% del otro anuncio.
- m2: dentro de ±dedup_m2_margin m2 del otro anuncio.
- bedrooms y bathrooms: coincidencia exacta.
- zona: ver _same_zona() más abajo — MISMO ESPÍRITU que matching.py usa
  para filters.zona, pero con una asimetría real e inevitable: la tabla
  listings NO tiene columna address (nunca se ha guardado, solo
  municipality), así que solo el anuncio recién scrapeado en esta misma
  ejecución (que sí trae su address en memoria, antes de guardarse) puede
  usarse para el lado "contiene la localidad" de la comparación. El anuncio
  ya existente en BD solo aporta su municipality.
- Comparación siempre entre listings de DOS PLATAFORMAS DISTINTAS
  (platform_id diferente) — el dedup dentro de una misma plataforma ya lo
  resuelve dedup_hash+platform_id, esto no lo toca.
"""
import uuid

import db
import matching


def mark_possible_duplicates(nuevos_listings: list[dict]) -> None:
    """nuevos_listings: uno por cada anuncio NUEVO insertado en esta
    ejecución (de cualquier plataforma), con su id de BD ya asignado y los
    campos price/m2/bedrooms/bathrooms/municipality/address/platform_id
    (ver _process_platform en main.py)."""
    if not nuevos_listings:
        return

    price_margin_pct = db.get_app_setting("dedup_price_margin_pct", 3.0)
    m2_margin = db.get_app_setting("dedup_m2_margin", 5.0)

    disponibles = db.get_available_listings()

    for nuevo in nuevos_listings:
        candidatos = [
            existente
            for existente in disponibles
            if existente["platform_id"] != nuevo["platform_id"]
            and existente["id"] != nuevo["id"]
            and _is_possible_duplicate(nuevo, existente, price_margin_pct, m2_margin)
        ]
        if not candidatos:
            continue

        # Si alguno de los candidatos ya pertenece a un grupo (porque ya
        # había sido marcado duplicado antes, en esta misma pasada o en una
        # anterior), se reutiliza ese grupo en vez de crear uno nuevo — así
        # un tercer/cuarto anuncio del mismo inmueble se suma al grupo que
        # ya existía sin caso especial. Si dos candidatos trajeran grupos
        # YA EXISTENTES distintos entre sí (caso raro: dos grupos previos
        # que resultan ser el mismo inmueble), se unifican bajo el primero
        # — no se fusiona ningún dato de los anuncios, solo la etiqueta de
        # agrupación.
        grupos_existentes = [c["duplicate_group_id"] for c in candidatos if c.get("duplicate_group_id")]
        group_id = grupos_existentes[0] if grupos_existentes else str(uuid.uuid4())

        db.mark_listing_duplicate(nuevo["id"], group_id)
        nuevo["duplicate_group_id"] = group_id

        for existente in candidatos:
            if existente.get("duplicate_group_id") != group_id:
                db.mark_listing_duplicate(existente["id"], group_id)
                existente["duplicate_group_id"] = group_id


def _is_possible_duplicate(nuevo: dict, existente: dict, price_margin_pct: float, m2_margin: float) -> bool:
    price_a, price_b = nuevo.get("price"), existente.get("price")
    if price_a is None or price_b is None or float(price_b) == 0:
        return False
    if abs(float(price_a) - float(price_b)) / float(price_b) * 100 > price_margin_pct:
        return False

    m2_a, m2_b = nuevo.get("m2"), existente.get("m2")
    if m2_a is None or m2_b is None:
        return False
    if abs(float(m2_a) - float(m2_b)) > m2_margin:
        return False

    if nuevo.get("bedrooms") is None or nuevo["bedrooms"] != existente.get("bedrooms"):
        return False
    if nuevo.get("bathrooms") is None or nuevo["bathrooms"] != existente.get("bathrooms"):
        return False

    return _same_zona(nuevo, existente)


def _same_zona(nuevo: dict, existente: dict) -> bool:
    nuevo_municipio = nuevo.get("municipality")
    existente_municipio = existente.get("municipality")
    if nuevo_municipio and existente_municipio:
        if matching.normalize(nuevo_municipio) == matching.normalize(existente_municipio):
            return True

    # Ver docstring del módulo: listings no guarda address, así que solo el
    # lado "nuevo" (recién scrapeado, todavía en memoria) puede aportarla.
    nuevo_direccion = nuevo.get("address")
    if nuevo_direccion and existente_municipio:
        if matching.normalize(existente_municipio) in matching.normalize(nuevo_direccion):
            return True

    return False
