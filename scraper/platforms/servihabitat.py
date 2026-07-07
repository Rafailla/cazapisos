"""Scraper de Servihabitat.

El sitio (Liferay) es server-rendered: las tarjetas de resultado, incluido un
bloque de datos estructurados para GTM, están en el HTML crudo de la primera
petición. Comprobado contra el sitio real (2026-07-07): requests + BeautifulSoup
es suficiente, no hace falta Playwright para esto.

Limitaciones conocidas de esta prueba de concepto:
- Orden "Novedad": el desplegable "Ordenar por" envía por GET el parámetro
  `_busqueda_WAR_servihabitatretailbusquedaportlet_order` (2 = Novedad), pero se
  comprobó empíricamente (mismos resultados con order=2 y order=3) que ese
  parámetro por sí solo no reordena nada — el sitio necesita sesión/estado de
  portlet Liferay, no solo query string. Se usa el orden que devuelve el sitio
  por defecto; la deduplicación por external_id en Supabase evita reprocesar
  anuncios ya vistos en ejecuciones sucesivas.
- Paginación: la página inicial trae como mucho ~20 tarjetas aunque el atributo
  `data-total` sea mayor (visto en Granada: 20 de 22 con `?_busqueda_..._cur=2`
  devolviendo exactamente el mismo HTML). El resto se carga por scroll infinito
  contra un endpoint con un token ofuscado (`data-iterator-url`) que no se ha
  conseguido invocar por GET directo. Para este PoC solo se procesa la primera
  página. Zonas con pocos resultados (ej. Málaga, 11 en total) quedan cubiertas
  por completo; si hace falta cobertura completa en zonas grandes, la vía
  pendiente es un fallback con Playwright que haga scroll real.
- "Promociones comerciales" (tarjetas con clase `list-product-buscador-promo`,
  categoría `promocioncomercial`): son paquetes de varios inmuebles vendidos
  juntos, con su propia URL (`/es/venta/promociones/vivienda/...`) y un precio
  que es el del paquete, no el de una vivienda individual. No encajan en el
  esquema de `listings` (un inmueble = una fila) y se omiten en este PoC.
"""
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.servihabitat.com"
SEARCH_PATH = "/es/venta/vivienda/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; cazapisos-bot/1.0)"}

_HREF_RE = re.compile(r"^/es/venta/vivienda")
_PROPERTY_TYPE_RE = re.compile(r"/vivienda-([a-z]+)/")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


def fetch_listings(zona_provincia: str) -> list[dict]:
    """Descarga y parsea la primera página de resultados para una provincia
    (slug simple, ej. "granada", "malaga"). Ver limitaciones en el docstring
    del módulo."""
    url = urljoin(BASE_URL + SEARCH_PATH, zona_provincia)
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.find_all("div", class_="list-product-buscador")
    return [_parse_card(card) for card in cards]


def _parse_card(card) -> dict:
    external_id = card.get("data-id")

    link = card.find("a", href=_HREF_RE)
    href = link["href"] if link else None
    url = urljoin(BASE_URL, href) if href else None

    property_type = None
    if href:
        match = _PROPERTY_TYPE_RE.search(href)
        if match:
            property_type = match.group(1)

    price = None
    price_el = card.find(id="price")
    if price_el:
        digits = re.sub(r"[^\d]", "", price_el.get_text())
        price = int(digits) if digits else None

    m2 = _extract_number(card.find(id="superficie"))
    bedrooms = _extract_number(card.find(id="numero-hab"))
    bathrooms = _extract_number(card.find(id="numero-ban"))

    municipality = None
    address = card.find(id="description")
    if address:
        spans = [s.get_text(strip=True) for s in address.find_all("span")]
        spans = [s for s in spans if s]
        if len(spans) >= 2:
            municipality = spans[-2].rstrip(",").strip()

    tags = []
    if card.find(class_="etiqueta-novedad"):
        tags.append("novedad")
    if card.find(class_="precio-negociable"):
        tags.append("precio_negociable")
    for el in card.find_all(class_="incluye-otros-list"):
        es_llaves = "llaves" in el.get("class", [])
        tags.append("llaves_no_disponibles" if es_llaves else "incluye_otros_inmuebles")

    return {
        "external_id": external_id,
        "url": url,
        "price": price,
        "property_type": property_type,
        "bedrooms": int(bedrooms) if bedrooms is not None else None,
        "bathrooms": int(bathrooms) if bathrooms is not None else None,
        "m2": m2,
        "municipality": municipality,
        "tags": tags,
    }


def _extract_number(el) -> float | None:
    if el is None:
        return None
    match = _NUMBER_RE.search(el.get_text())
    if not match:
        return None
    return float(match.group().replace(",", "."))
