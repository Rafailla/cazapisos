"""Scraper de Aliseda.

Investigación real contra el sitio (2026-07-09):
- La URL correcta es https://www.alisedainmobiliaria.com/ — OJO: aliseda.es
  es el ayuntamiento del pueblo de Aliseda (Cáceres), un sitio totalmente
  distinto (portal Liferay del consistorio), no la inmobiliaria. Se detectó
  a tiempo por el theme "caceresayto" en el HTML antes de seguir por ahí.
- NO es server-rendered: es una SPA Angular (mismo patrón que Solvia — bundle
  main-*.js, sin contenido de tarjetas en el HTML inicial). No hizo falta
  Playwright: en vez de renderizar, se abrió el sitio real con el navegador
  (claude-in-chrome) para capturar en la pestaña de Red la llamada XHR real
  que hace la SPA al buscar, y se replicó esa llamada con requests.
- Sin protección anti-bot detectada (sin Cloudflare, sin captcha) en varias
  peticiones a la API.
- Endpoint de búsqueda real (backend Laravel, dominio distinto del sitio):
      GET https://laravel.alisedainmobiliaria.com/api/v2/new-search
      params: tipo=10 (residencial — sin este filtro salen también otros
              FkTipo, p.ej. 8), provincia=<slug-minusculas> (ej. "malaga",
              "granada" — OJO: el parámetro correcto es "provincia", NO
              "provinciaUrl", que es solo el nombre del campo de vuelta en
              cada resultado; "provinciaUrl=malaga" NO filtra nada),
              paginationSize=<N> (el backend igualmente limita a 12 por
              página pase lo que pase — hay que paginar de verdad con
              page=1,2,3...).
      headers: Accept: application/json, Referer: https://www.
               alisedainmobiliaria.com/inmuebles (sin esto también
               responde bien en las pruebas, pero se manda por si acaso).
  Inventario real y pequeño: Málaga tipo=10 → 25 resultados (3 páginas de
  ~12), Granada tipo=10 → 11 (1 página). No hace falta límite de PoC de "solo
  primera página" como en otras plataformas: con esta paginación real y un
  inventario tan pequeño, se trae TODO en cada ejecución.
- HALLAZGO IMPORTANTE — Aliseda y Anticipa comparten el mismo backend y el
  MISMO inventario: se comprobó pidiendo la misma búsqueda de Málaga con
  Referer de alisedainmobiliaria.com y con Referer de anticipa.com contra
  este mismo laravel.alisedainmobiliaria.com — devuelven el conjunto de ids
  IDÉNTICO (25/25 iguales). Los ids de cada resultado llevan un prefijo que
  delata el origen de la cartera (ej. "ant..." = Anticipa, "srb..." =
  probablemente Sareb, "vtr...", "gor...", o solo numérico), pero TODOS se
  venden a través del mismo escaparate compartido, con Aliseda y Anticipa
  como dos marcas/webs distintas sobre los mismos inmuebles. Por eso NO se
  ha implementado scraper/platforms/anticipa.py aparte: hacerlo escrapeando
  anticipa.com duplicaría cada anuncio (mismo external_id físico) bajo un
  platform_id distinto, rompiendo la regla de "un inmueble = una fila" y
  generando alertas duplicadas por email para el mismo piso real. La fila
  de Anticipa en `platforms` se deja con active=false y notas explicando
  esto — igual tratamiento que una plataforma descartada por anti-bot,
  aunque el motivo aquí es otro (deduplicación, no protección).
- URL de ficha de cada anuncio: /inmueble/{id} (confirmado con la propia
  SPA — al hacer click en una tarjeta real, el link es exactamente ese
  patrón, sin necesidad de construir slugs de ciudad/tipo).
- Estructura de cada resultado (JSON ya estructurado, no HTML):
    - id: external_id (ej. "ant00030693245", "vtr0200332474", o solo
      numérico como "50634359" — según cartera de origen).
    - operacion.Precio: price.
    - vivienda.Bedrooms / vivienda.Bathrooms: bedrooms / bathrooms.
    - ConstructedArea (nivel raíz): m2.
    - address.Ciudad: municipio (viene en mayúsculas, ej. "ABARÁN" — se
      pasa a formato título).
    - address.TipoVia + StreetName + StreetNumber: para la dirección.
    - vivienda.Piscina / PiscinaComunitaria / PiscinaPropia: has_pool (true
      si cualquiera de las tres es 1) — viene directo, no hace falta cruzar
      tags como en Servihabitat/Pisos.com.
    - Estrenar (0/1, nivel raíz): se usa como condition — 1="nueva",
      0="segunda_mano". Es el campo más literal encontrado ("estrenar" =
      usar por primera vez / a estrenar = obra nueva). Existe también un
      campo "redComercial" con valores "Obra nueva"/"Segunda mano" que en
      la práctica NO coincide de forma fiable con Estrenar en la misma
      muestra (11 de 12 anuncios de Málaga tenían redComercial="Obra
      nueva" pero solo 5 de esos 12 tenían Estrenar=1) — parece ser una
      etiqueta de canal/red comercial, no el estado real del inmueble, así
      que se descarta a favor de Estrenar.
    - property_type: no hay un campo de texto limpio (solo códigos
      numéricos FkSubtipo sin tabla de traducción encontrada). Se
      aproxima buscando palabras clave de tipo (piso/chalet/casa/
      apartamento/ático/dúplex/adosado/villa) al principio de la
      Description; si no aparece ninguna, se deja en None en vez de
      inventar un tipo — property_type no lo usa ningún filtro activo
      ahora mismo (todos están con property_type=null), así que esta
      limitación no bloquea el matching real.

Limitaciones conocidas de este PoC:
- property_type es un best-effort por palabras clave, no siempre fiable.
- condition depende de Estrenar, que es un campo de la propia ficha —
  fiable en el sentido de que es literal del inmueble, pero no se ha
  podido contrastar de forma independiente.
"""
import re

import requests

BASE_URL = "https://www.alisedainmobiliaria.com"
API_URL = "https://laravel.alisedainmobiliaria.com/api/v2/new-search"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; cazapisos-bot/1.0)",
    "Accept": "application/json",
    "Referer": f"{BASE_URL}/inmuebles",
}

# FkTipo=10 = residencial (vivienda). Sin este filtro salen también otros
# tipos de inmueble (ej. FkTipo=8) mezclados en el mismo listado.
_TIPO_RESIDENCIAL = 10

_TYPE_KEYWORDS = [
    "piso", "chalet adosado", "chalet", "casa", "apartamento", "ático",
    "atico", "dúplex", "duplex", "adosado", "villa",
]
_TYPE_RE = re.compile("|".join(re.escape(k) for k in _TYPE_KEYWORDS), re.IGNORECASE)


def fetch_listings(province_slug: str) -> list[dict]:
    """Todos los resultados residenciales de una provincia (slug simple, ej.
    "granada", "malaga"), paginando de verdad (el backend limita a ~12 por
    página). Inventario real pequeño (decenas), así que se trae todo."""
    listings = []
    page = 1
    while True:
        response = requests.get(
            API_URL,
            params={
                "tipo": _TIPO_RESIDENCIAL,
                "paginationSize": 50,
                "provincia": province_slug,
                "page": page,
            },
            headers=HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        for item in data.get("data", []):
            listing = _parse_item(item)
            if listing is not None:
                listings.append(listing)

        if page >= data.get("last_page", page):
            break
        page += 1

    return listings


def fetch_tagged_ids(province_slug: str, tag: str) -> set[str]:
    """Aliseda no necesita cruzar tags: piscina y condición vienen directas
    en cada resultado (ver fetch_listings/_parse_item). Se devuelve siempre
    un conjunto vacío — main.py cae de vuelta a listing["has_pool"]/
    listing["condition"] ya resueltos aquí."""
    return set()


def _parse_item(item: dict) -> dict | None:
    external_id = item.get("id")
    if not external_id:
        return None

    address = item.get("address") or {}
    operacion = item.get("operacion") or {}
    vivienda = item.get("vivienda") or {}

    municipality = address.get("Ciudad")
    municipality = municipality.title() if municipality else None

    calle_parts = [
        address.get("TipoVia"),
        address.get("StreetName"),
        address.get("StreetNumber"),
    ]
    direccion = " ".join(str(p) for p in calle_parts if p) or None

    estrenar = item.get("Estrenar")
    condition = "nueva" if estrenar == 1 else "segunda_mano" if estrenar == 0 else None

    has_pool = bool(
        vivienda.get("Piscina") or vivienda.get("PiscinaComunitaria") or vivienda.get("PiscinaPropia")
    )

    property_type = None
    description = item.get("Description") or ""
    match = _TYPE_RE.search(description)
    if match:
        property_type = match.group().lower()

    return {
        "external_id": external_id,
        "url": f"{BASE_URL}/inmueble/{external_id}",
        "price": operacion.get("Precio"),
        "property_type": property_type,
        "bedrooms": vivienda.get("Bedrooms"),
        "bathrooms": vivienda.get("Bathrooms"),
        "m2": item.get("ConstructedArea"),
        "municipality": municipality,
        "address": direccion,
        "tags": [],
        "has_pool": has_pool,
        "condition": condition,
    }
