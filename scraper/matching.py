"""Comprueba un listing contra los perfiles de búsqueda de la tabla `filters`."""
import unicodedata


def normalize(text: str) -> str:
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def matches_any_filter(listing: dict, filters: list[dict]) -> list[str]:
    return [f["id"] for f in filters if _matches_one(listing, f)]


def _matches_one(listing: dict, f: dict) -> bool:
    # price_min existe en el esquema pero el criterio de match solo contempla
    # price_max, bedrooms_min, bathrooms_min, m2_min y property_type.
    price_max = f.get("price_max")
    if price_max is not None:
        if listing.get("price") is None or listing["price"] > float(price_max):
            return False

    bedrooms_min = f.get("bedrooms_min")
    if bedrooms_min is not None:
        if listing.get("bedrooms") is None or listing["bedrooms"] < bedrooms_min:
            return False

    bathrooms_min = f.get("bathrooms_min")
    if bathrooms_min is not None:
        if listing.get("bathrooms") is None or listing["bathrooms"] < bathrooms_min:
            return False

    m2_min = f.get("m2_min")
    if m2_min is not None:
        if listing.get("m2") is None or listing["m2"] < float(m2_min):
            return False

    property_type = f.get("property_type")
    if property_type:
        if not listing.get("property_type") or normalize(listing["property_type"]) != normalize(property_type):
            return False

    zona = f.get("zona")
    if zona:
        localidades = [normalize(loc) for loc in zona.split(",") if loc.strip()]
        municipality = listing.get("municipality")
        address = listing.get("address")
        matches_municipality = bool(municipality) and normalize(municipality) in localidades
        # Algunas localidades de zona son barrios/urbanizaciones (ej. "La
        # Termica") que no aparecen como municipality sino dentro de la
        # dirección completa de la tarjeta (calle/urbanización).
        matches_address = bool(address) and any(loc in normalize(address) for loc in localidades)
        if not (matches_municipality or matches_address):
            return False

    if f.get("requires_pool") and not listing.get("has_pool"):
        return False

    property_condition = f.get("property_condition")
    if property_condition and listing.get("condition") != property_condition:
        return False

    return True
