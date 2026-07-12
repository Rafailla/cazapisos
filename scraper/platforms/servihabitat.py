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
- Filtros por característica sin visitar cada ficha: el sitio tiene URLs del
  tipo /es/venta/vivienda/{provincia}/t-{tag} (tags vistos: "piscina",
  "aestrenar", "segundamano"). No se pueden combinar varios "t-" en una URL
  (probado: /t-piscina/t-aestrenar da 404). CONFIRMADO EN REAL (2026-07-08):
  cuando una combinación provincia+tag no tiene ningún resultado real
  (`data-total="0"` en el div `.product-list`), el sitio hace el mismo
  fallback "viviendas cerca de X" ya documentado para zonas — la página SIGUE
  trayendo tarjetas con class="list-product-buscador" (no promo) de anuncios
  que NO tienen esa característica. Ejemplo real: granada/t-aestrenar tiene
  data-total="0" y aun así devuelve 17 tarjetas normales del resto del
  catálogo de Granada. `fetch_tagged_ids` comprueba data-total antes de
  confiar en las tarjetas; si es "0", devuelve un conjunto vacío.

Ascensor y planta (sesión 2026-07-11, filtros nuevos):
- Ascensor: t-ascensor es un filtro URL real igual que t-piscina —
  comprobado con datos reales (Málaga: 12 tarjetas sin filtrar -> 3 con
  t-ascensor, conjunto realmente distinto, mismo patrón que piscina). No
  hizo falta tocar este módulo: fetch_tagged_ids ya es genérica para
  cualquier tag, "ascensor" funciona automáticamente en cuanto main.py lo
  pida (ver PLATFORM_TAG_FETCHERS/tag_fetch en main.py).
- Planta: NO se encontró ninguna señal fiable. Se investigó: (a) las
  tarjetas de resultado tienen un bloque de datos analítico con
  `productExtra: [...]` (lift/swimming-pool/garage/...) — "lift" confirma
  ascensor, pero ese array no incluye nunca planta; (b) el sitio SÍ tiene
  checkboxes de filtro "Ático"/"Planta baja", pero son en realidad
  subtipos de vivienda (subtipologia_vivienda2/4), no un atributo de
  planta independiente; (c) probado /t-atico, /t-plantabaja, /t-bajo como
  URLs — ninguno filtra de verdad (mismas 12 tarjetas que sin filtro,
  igual que el patrón ya documentado de "fallback cerca de"). Conclusión:
  Servihabitat no expone la planta del anuncio en ningún sitio accesible
  sin abrir cada ficha individual — floor queda siempre en None.
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
    address_text = None
    address = card.find(id="description")
    if address:
        spans = [s.get_text(strip=True) for s in address.find_all("span")]
        spans = [s for s in spans if s]
        if len(spans) >= 2:
            municipality = spans[-2].rstrip(",").strip()
        if spans:
            # Texto completo (calle/urbanización + municipio + provincia), para
            # matching.py: algunas localidades de filters.zona son barrios o
            # urbanizaciones (ej. "La Termica") que no aparecen en
            # `municipality` sino en el tramo de la calle/urbanización.
            address_text = ", ".join(spans)

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
        "address": address_text,
        "tags": tags,
    }


def fetch_tagged_ids(province_slug: str, tag: str) -> set[str]:
    """external_id de los anuncios reales (no promos) etiquetados con `tag`
    (ej. "piscina", "aestrenar", "segundamano") para una provincia. Devuelve
    un conjunto vacío si el sitio no tiene ningún resultado real para esa
    combinación (ver nota de "cerca de" en el docstring del módulo) — nunca
    hace falta abrir la ficha de cada anuncio para saber esto."""
    url = urljoin(BASE_URL + SEARCH_PATH, f"{province_slug}/t-{tag}")
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")
    product_list = soup.find("div", class_="product-list")
    total = product_list.get("data-total") if product_list else None
    if total in (None, "0"):
        return set()

    cards = soup.find_all("div", class_="list-product-buscador")
    return {card.get("data-id") for card in cards if card.get("data-id")}


def _extract_number(el) -> float | None:
    if el is None:
        return None
    match = _NUMBER_RE.search(el.get_text())
    if not match:
        return None
    return float(match.group().replace(",", "."))
