"""Scraper de Pisos.com.

Investigación real contra el sitio (2026-07-09):
- Server-rendered (requests + BeautifulSoup de sobra, no hace falta Playwright).
  Sin Cloudflare, sin captcha, sin ninguna protección anti-bot detectada en
  varias decenas de peticiones seguidas (búsqueda por provincia, por
  municipio, con filtro de piscina, con orden "más recientes" — todas 200 OK
  y con el HTML de resultados de verdad, no una página de reto/challenge).
- Búsqueda por provincia: https://www.pisos.com/venta/pisos-{provincia}/
  (ej: malaga, granada). También hay URLs por municipio
  (/venta/pisos-cartama/, /venta/pisos-marbella/...) — no se usan aquí porque
  fetch_listings() escrapea a nivel provincia, igual que Servihabitat, y deja
  el filtrado por zona a matching.py; quedan documentadas por si en el futuro
  compensa escrapear por municipio en vez de por provincia para tener mejor
  cobertura de zonas concretas (ver "Limitaciones" más abajo).
- A diferencia de Servihabitat, el orden "Más recientes" SÍ funciona de
  verdad por URL: añadiendo /fecharecientedesde-desc/ al final de la ruta de
  búsqueda cambia realmente el orden de los resultados (comprobado: los ids
  de tarjeta son distintos entre el orden por defecto y este). Se usa
  siempre para maximizar la posibilidad de coger anuncios nuevos en la
  primera página.
- Paginación real por ruta: .../2/, .../3/... (visto en el pie de página,
  "Siguiente" enlaza a esas rutas). No implementada en este PoC — solo se
  pide la primera página (~30 tarjetas), igual límite de alcance que
  Servihabitat. Con inventario tan grande (30k+ anuncios por provincia en
  Málaga o Granada) la primera página por fecha de publicación no cubre ni
  de lejos todo, pero sí va enseñando lo más reciente de TODA la provincia
  en cada ejecución, y con ejecuciones diarias + deduplicación por
  external_id se van acumulando los anuncios que van entrando.
- Filtro por piscina vía URL real: /venta/pisos-{provincia}/piscina/ (con o
  sin orden). Confirmado que reduce de verdad el total de resultados
  (Málaga: 35.907 sin filtrar -> 23.407 con piscina) — no es un adorno
  cosmético como el "orden" roto de Servihabitat. Las tarjetas son
  individuales (mismo formato que la búsqueda normal, con precio único).
- "Obra nueva" / "segunda mano": el sitio SÍ tiene una sección separada de
  obra nueva (/promociones-{provincia}/), pero cada tarjeta ahí es una
  PROMOCIÓN (desarrollo con varias viviendas: precio "Desde X €" y un rango
  de m2, ej. "171 m² - 420 m²", URL /promocion-.../ en vez de /comprar-.../).
  Igual que las tarjetas "Promoción comercial" de Servihabitat, no encajan
  en el esquema de listings (un inmueble = una fila) y se EXCLUYEN. No hay
  ningún filtro URL equivalente a t-segundamano de Servihabitat, pero no
  hace falta: al ser la obra nueva un catálogo aparte (/promociones-.../),
  todo lo que devuelve fetch_listings() (que usa /venta/pisos-.../, nunca
  /promociones-.../) es de segunda mano por construcción del propio sitio,
  así que _parse_card() pone condition="segunda_mano" directamente — no es
  un valor inventado, es un hecho de cómo pisos.com organiza su catálogo.
- Estructura de cada tarjeta (class="ad-preview", excluyendo las que están
  dentro de /promocion-.../ o cuyo id de tarjeta no lleva a /comprar/):
    - id del div = external_id (ej. "62501335970.109800").
    - <a class="ad-preview__title" href="/comprar/...">Piso en ...</a>:
      el enlace, y la primera palabra del texto es el tipo de vivienda
      (Piso/Casa/Chalet/Apartamento/Ático/Dúplex...).
    - <p class="ad-preview__subtitle">Barrio (Distrito X. Municipio
      Capital)</p> o "Barrio (Municipio)" o solo "Municipio" si no hay
      barrio — formato variable, ver _extract_municipality().
    - <span class="ad-preview__price">560.000 €</span> o "A consultar".
    - <p class="ad-preview__char"> por cada característica presente:
      "3 habs.", "2 baños", "122 m²" (a veces con separador de miles,
      "1.004 m²"), y a veces un piso/planta ("Bajo", "1ª planta") que no es
      ninguna de las anteriores y se ignora.

Limitaciones conocidas de este PoC (mismo espíritu que Servihabitat):
- Solo primera página por provincia (~30 tarjetas) y primera página del
  filtro de piscina (~30 tarjetas) — no se pagina.
- Zona: fetch_listings() no filtra por municipio/barrio, igual que
  Servihabitat — matching.py se encarga con listing['address'].
"""
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.pisos.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; cazapisos-bot/1.0)"}

_HREF_RE = re.compile(r"^/comprar/")
_NUMBER_RE = re.compile(r"[\d.,]+")


def fetch_listings(province_slug: str) -> list[dict]:
    """Primera página de resultados (orden "más recientes") para una
    provincia (slug simple, ej. "granada", "malaga"). Ver limitaciones en el
    docstring del módulo."""
    url = urljoin(BASE_URL, f"/venta/pisos-{province_slug}/fecharecientedesde-desc/")
    return _fetch_cards(url)


def fetch_tagged_ids(province_slug: str, tag: str) -> set[str]:
    """external_id de la primera página de resultados con una característica
    (por ahora solo "piscina" tiene un filtro URL real y fiable en Pisos.com
    — para cualquier otro tag se devuelve un conjunto vacío en vez de
    inventar una URL que no se ha confirmado)."""
    if tag != "piscina":
        return set()

    url = urljoin(BASE_URL, f"/venta/pisos-{province_slug}/piscina/fecharecientedesde-desc/")
    cards = _fetch_cards(url)
    return {listing["external_id"] for listing in cards if listing.get("external_id")}


def _fetch_cards(url: str) -> list[dict]:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.find_all("div", class_="ad-preview")

    listings = []
    for card in cards:
        listing = _parse_card(card)
        if listing is not None:
            listings.append(listing)
    return listings


def _parse_card(card) -> dict | None:
    link = card.find("a", class_="ad-preview__title")
    href = link.get("href") if link else None
    if not href or not _HREF_RE.match(href):
        # Excluye promociones (/promocion-.../) y cualquier tarjeta sin
        # enlace a un anuncio individual — no encajan en "un inmueble = una fila".
        return None

    external_id = card.get("id")
    url = urljoin(BASE_URL, href)
    title = link.get_text(strip=True)
    property_type = title.split(" ")[0].lower() if title else None

    price = None
    price_el = card.find("span", class_="ad-preview__price")
    if price_el:
        digits = re.sub(r"[^\d]", "", price_el.get_text())
        price = int(digits) if digits else None

    bedrooms = bathrooms = m2 = None
    for char_el in card.find_all("p", class_="ad-preview__char"):
        text = char_el.get_text(strip=True)
        lowered = text.lower()
        if "hab" in lowered:
            bedrooms = _to_int(_parse_number(text))
        elif "baño" in lowered or "bano" in lowered:
            bathrooms = _to_int(_parse_number(text))
        elif "m²" in lowered or "m2" in lowered:
            m2 = _parse_number(text)

    subtitle_el = card.find("p", class_="ad-preview__subtitle")
    subtitle = subtitle_el.get_text(strip=True) if subtitle_el else None
    municipality = _extract_municipality(subtitle)

    return {
        "external_id": external_id,
        "url": url,
        "price": price,
        "property_type": property_type,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "m2": m2,
        "municipality": municipality,
        "address": subtitle,
        "tags": [],
        # Hecho estructural del catálogo, no un cruce de tags como en
        # Servihabitat: ver nota de "Obra nueva" / "segunda mano" arriba.
        "condition": "segunda_mano",
    }


def _extract_municipality(subtitle: str | None) -> str | None:
    """"Barrio (Distrito X. Municipio Capital)" -> "Municipio"
    "Barrio (Municipio)" -> "Municipio"
    "Municipio" (sin barrio) -> "Municipio" tal cual."""
    if not subtitle:
        return None

    match = re.search(r"\(([^)]+)\)\s*$", subtitle)
    if not match:
        return subtitle.strip()

    inner = match.group(1)
    if ". " in inner:
        inner = inner.split(". ")[-1]
    inner = inner.strip()
    if inner.endswith(" Capital"):
        inner = inner[: -len(" Capital")]
    return inner.strip()


def _parse_number(text: str) -> float | None:
    """Números en formato español: "1.004" (miles) -> 1004, "50,5" (decimal)
    -> 50.5."""
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    raw = match.group().replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _to_int(value: float | None) -> int | None:
    return int(value) if value is not None else None
