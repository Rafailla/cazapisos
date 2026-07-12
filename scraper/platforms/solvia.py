"""Scraper de Solvia.

Investigación real contra el sitio (2026-07-09):
- NO es server-rendered para los resultados: /es/comprar/viviendas es una SPA
  Angular (Angular Universal SSR de la shell, pero el listado de anuncios se
  pide por JS al cargar). Confirmado con requests+BeautifulSoup: todas las
  coincidencias de "habitaciones"/"precio"/"m2" en el HTML servido eran
  strings de traducción i18n embebidas ({"rooms":"habitaciones"}...), no
  tarjetas reales. No hizo falta Playwright: en vez de renderizar la SPA, se
  encontró y usa directamente la API JSON que la propia SPA llama.
- Sin protección anti-bot detectada (sin Cloudflare, sin captcha) en varias
  decenas de peticiones a la API, incluida una respuesta grande de 5.4MB.
- Endpoint de búsqueda real:
      POST https://www.solvia.es/api/inmuebles/v1/buscarInmuebles
      body JSON: {"idProvincia": <id>}
      headers: Content-Type: application/json,
               Accept: application/json, text/plain, */*,
               Referer: https://www.solvia.es/es/comprar/viviendas
  Sin estos headers (solo User-Agent) responde 406 Not Acceptable — hace
  falta Accept/Referer para que la API acepte la petición.
  idProvincia: Granada = 18, Málaga = 29 (sacado de /api/spi/v1/provincias).
  Devuelve TODOS los resultados en una sola llamada, sin paginar (Málaga:
  265/265 en una respuesta, "paginacion":{"tamanoPagina":265}) — mejor
  cobertura que Servihabitat/Pisos.com, que limitan a ~20-30 por página.
- Se investigó /api/spi/v1/inmuebles (prefijo /spi/) pensando que podía ser
  el buscador: es en realidad una herramienta de consulta por referencia
  catastral (exige un parámetro "query" que valida contra el regex de una
  referencia catastral de 20 caracteres) — descartado, no es el buscador.
- Los resultados de buscarInmuebles mezclan TODAS las categorías de
  inmuebles (viviendas, garajes, locales, suelo, trasteros, naves,
  edificios...), no solo residencial. Se filtra por
  categoriaTipoVivienda.id == "1" (Piso/Casa/Chalet/Apartamento/Ático/
  Dúplex — confirmado inspeccionando los 265 resultados de Málaga: id "1"
  agrupa solo tipos residenciales, "2" son garajes, "3" locales/oficinas,
  "4" suelo, "10" trasteros, "7" naves, "8" edificios, "11" "En
  Construccion" aparte).
- Piscina: viene directo en cada resultado (caracteristicas.piscina, bool),
  no hace falta cruzar contra una URL filtrada aparte como en
  Servihabitat/Pisos.com. Por eso fetch_tagged_ids() no se usa para
  "piscina" — has_pool se resuelve en el propio fetch_listings().
- Obra nueva / segunda mano: no se consiguió acceder al catálogo de
  promociones para confirmarlo con datos (link /es/obra-nueva, endpoints
  /api/inmuebles/v1/promociones y /api/inmuebles/v1/promociones/@id/
  inmuebles vistos en el HTML), pero:
    - GET /api/inmuebles/v1/promociones?idProvincia=29 (y variantes con
      provincia=, provinciaId=, pagina=, sin ningún parámetro) -> siempre
      400 Bad Request con cuerpo VACÍO (Content-Length: 0), a diferencia
      del 400 de buscarInmuebles/otros endpoints, que sí devuelven JSON
      con el detalle del error de validación — esto (más la cabecera
      CF-Ray presente en la respuesta) sugiere que el 400 aquí lo pone un
      WAF/gateway de Cloudflare delante del backend real, no la propia
      app Java, así que no hay pista de validación que seguir por ese
      lado (reintentado sesión 2026-07-11: mismo resultado con headers
      completos tipo navegador — Accept-Language, Origin — no solo
      Accept/Referer).
    - POST /api/inmuebles/v1/promociones {"idProvincia":29} -> 405 Method
      Not Allowed (confirmado también con body vacío y con
      {"provincia":{"id":29}}).
    - POST /api/inmuebles/v1/buscarPromociones y GET
      /api/inmuebles/v1/promociones/buscar (nombres de endpoint por
      analogía con buscarInmuebles) -> 404 Not Found, no existen.
    - GET /api/inmuebles/v2/promociones?idProvincia=29 -> mismo patrón que
      ya se vio con buscarInmuebles en v2: 400 con
      "Identificador de inmueble [promociones] no válido", es decir v2
      NO tiene una ruta de promociones propia, "promociones" se
      interpreta como un id contra /api/inmuebles/v2/@id — descartado
      igual que v2 para buscarInmuebles.
  No se encontró la forma correcta de pedir ese catálogo tras dos sesiones
  de intentos razonables (2026-07-09 y 2026-07-11) — se deja documentado
  y no se sigue insistiendo, es una mejora menor (afecta solo a si
  condition puede ser "nueva" para Solvia, no bloquea nada crítico). Sin
  embargo, igual que en Pisos.com, la existencia de ese catálogo aparte
  (obra nueva vive en /es/obra-nueva + /api/inmuebles/v1/promociones, NO
  en buscarInmuebles) es la misma evidencia estructural que justifica
  asumir que buscarInmuebles es el catálogo de segunda mano por
  construcción del sitio. El único indicio de obra nueva encontrado dentro
  de buscarInmuebles fue un resultado con categoriaTipoVivienda.id "11" =
  "En Construccion" — una categoría DISTINTA de "1" (residencial normal),
  que ya se excluye en _parse_item() junto con garajes/locales/suelo/etc.
  Dentro de categoriaTipoVivienda.id=="1" (Piso, Chalet, Apartamento,
  Dúplex, Casa, Ático) no se encontró ningún campo que indique obra nueva
  (etiquetaProducto, telefonoActivoObraNueva, fichaOrigenProducto,
  nComponentesModelo/nModelosPromocion — todos uniformes/vacíos en los 140
  residenciales de la muestra de Málaga). Por eso _parse_item() pone
  condition="segunda_mano" para categoría "1", con el mismo razonamiento
  que pisos.py: no es un valor inventado, es la consecuencia de cómo Solvia
  separa obra nueva en un catálogo aparte que buscarInmuebles no toca.
- Ascensor y planta (sesión 2026-07-11, filtros nuevos): investigado con
  datos reales (30 residenciales de Málaga inspeccionados) — no hay ningún
  campo de ascensor en el resultado (ni en caracteristicas ni en el nivel
  raíz). Para planta: "altura"/"alturaLibre" en caracteristicas están
  SIEMPRE a None y "nPlantas" SIEMPRE a 0 en los 30 comprobados —
  parecen campos de suelo/urbanismo sin rellenar para vivienda normal,
  no la planta del anuncio. Conclusión: Solvia genuinamente no expone
  ninguno de los dos — has_elevator y floor quedan siempre en None
  (nunca False/inventado).
- Página de ficha de cada anuncio (para construir la URL), patrón
  confirmado con petición real (200 OK):
      /es/comprar/{tipoVivienda.amigable}/{provincia.amigable}/
      {poblacion.amigable}/{id}
  (en minúsculas; ej. .../apartamento/malaga/marbella/173622-138472-o).
  No hay un campo de URL directo en el JSON, se construye a partir de esos
  tres campos + el id.
- Estructura de cada resultado (ya viene como JSON estructurado, no HTML):
    - id: external_id (ej. "173622-138472-O").
    - precio: price (float o null si no se muestra precio).
    - totalDormitorios: bedrooms.
    - totalBanyos: bathrooms.
    - m2: m2.
    - poblacion.name: municipio, ya limpio (sin parsing de subtítulo).
    - direccion: dirección (puede venir null).
    - tipoVivienda.amigable: property_type.
    - caracteristicas.piscina: has_pool.
    - categoriaTipoVivienda.id: usado solo para filtrar a residencial.

Limitaciones conocidas de este PoC:
- condition siempre "segunda_mano" por exclusión de catálogo (ver arriba),
  nunca "nueva" — si en el futuro se consigue acceder al catálogo de
  promociones, esto se podría refinar.
- Sin paginar manualmente: aunque la API no pagina los resultados (los
  devuelve todos en una sola llamada), esto depende de que el catálogo siga
  siendo tan pequeño; si Solvia crece mucho en una provincia habría que
  revisar si "paginacion" alguna vez limita el resultado.
"""
from urllib.parse import quote

import requests

BASE_URL = "https://www.solvia.es"
SEARCH_URL = f"{BASE_URL}/api/inmuebles/v1/buscarInmuebles"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; cazapisos-bot/1.0)",
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{BASE_URL}/es/comprar/viviendas",
    "Content-Type": "application/json",
}

# Slug de provincia (matching.py / Supabase) -> idProvincia de la API de Solvia.
PROVINCIA_IDS = {
    "granada": 18,
    "malaga": 29,
}

# categoriaTipoVivienda.id que corresponde a vivienda residencial (excluye
# garajes=2, locales/oficinas=3, suelo=4, trasteros=10, naves=7, edificios=8).
_CATEGORIA_RESIDENCIAL = "1"


def fetch_listings(province_slug: str) -> list[dict]:
    """Todos los resultados residenciales de una provincia (slug simple, ej.
    "granada", "malaga"). Ver limitaciones en el docstring del módulo."""
    id_provincia = PROVINCIA_IDS.get(province_slug)
    if id_provincia is None:
        return []

    response = requests.post(
        SEARCH_URL, json={"idProvincia": id_provincia}, headers=HEADERS, timeout=30
    )
    response.raise_for_status()
    data = response.json()

    listings = []
    for item in data.get("resultado", []):
        listing = _parse_item(item)
        if listing is not None:
            listings.append(listing)
    return listings


def fetch_tagged_ids(province_slug: str, tag: str) -> set[str]:
    """Solvia no necesita cruzar tags: piscina viene directo en cada
    resultado y condition se resuelve por catálogo (ver fetch_listings/
    _parse_item). Se devuelve siempre un conjunto vacío — main.py cae de
    vuelta a listing["has_pool"]/listing["condition"] ya resueltos aquí."""
    return set()


def _parse_item(item: dict) -> dict | None:
    categoria = (item.get("categoriaTipoVivienda") or {}).get("id")
    if categoria != _CATEGORIA_RESIDENCIAL:
        return None

    external_id = item.get("id")
    if not external_id:
        return None

    tipo = (item.get("tipoVivienda") or {}).get("amigable") or ""
    provincia = (item.get("provincia") or {}).get("amigable") or ""
    poblacion_amigable = (item.get("poblacion") or {}).get("amigable") or ""
    url = (
        f"{BASE_URL}/es/comprar/{quote(tipo.lower())}/{quote(provincia.lower())}/"
        f"{quote(poblacion_amigable.lower())}/{quote(external_id.lower())}"
    )

    caracteristicas = item.get("caracteristicas") or {}
    poblacion = item.get("poblacion") or {}

    return {
        "external_id": external_id,
        "url": url,
        "price": item.get("precio"),
        "property_type": tipo.lower() if tipo else None,
        "bedrooms": item.get("totalDormitorios"),
        "bathrooms": item.get("totalBanyos"),
        "m2": item.get("m2"),
        "municipality": poblacion.get("name"),
        "address": item.get("direccion"),
        "tags": [],
        "has_pool": bool(caracteristicas.get("piscina")),
        # Hecho estructural del catálogo (obra nueva vive aparte en
        # /es/obra-nueva), no un valor inventado — ver docstring del módulo.
        "condition": "segunda_mano",
        # Ascensor y planta: investigado (sesión 2026-07-11), Solvia
        # genuinamente no expone ninguno de los dos — ver docstring del
        # módulo. None explícito, nunca False/adivinado.
        "has_elevator": None,
        "floor": None,
    }
