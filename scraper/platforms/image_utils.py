"""Resolución de la URL de imagen principal de un <img> (BeautifulSoup Tag),
reutilizable entre scrapers de plataformas."""
import re
from urllib.parse import urljoin

_PLACEHOLDER_RE = re.compile(r"blank|placeholder|lazy|spacer", re.IGNORECASE)


def resolve_image_url(img_tag, base_url: str) -> str | None:
    """Prioridad de fuentes: srcset (candidato de mayor resolución, o el
    primero si no trae descriptores de ancho/densidad) -> data-src/
    data-lazy-src/data-original (lazy loading) -> src. Descarta placeholders
    (data: URIs/base64, "1x1", nombres tipo "blank"/"placeholder"/"lazy"/
    "spacer") y devuelve SIEMPRE una URL absoluta https (urljoin contra
    base_url, forzando el esquema si el origen ya era absoluto en http).
    Nunca lanza excepción hacia arriba: cualquier fallo devuelve None."""
    if img_tag is None:
        return None
    try:
        candidate = (
            _from_srcset(img_tag.get("srcset"))
            or img_tag.get("data-src")
            or img_tag.get("data-lazy-src")
            or img_tag.get("data-original")
            or img_tag.get("src")
        )
        if not candidate:
            return None
        candidate = candidate.strip()
        if not candidate or _is_placeholder(candidate):
            return None

        resolved = urljoin(base_url, candidate)
        if resolved.startswith("http://"):
            resolved = "https://" + resolved[len("http://") :]
        return resolved if resolved.startswith("https://") else None
    except Exception:
        return None


def _from_srcset(srcset: str | None) -> str | None:
    if not srcset:
        return None
    candidatos = []
    for part in srcset.split(","):
        bits = part.strip().split()
        if not bits:
            continue
        url = bits[0]
        width = None
        if len(bits) > 1 and bits[1].endswith("w"):
            try:
                width = int(bits[1][:-1])
            except ValueError:
                width = None
        candidatos.append((width, url))
    if not candidatos:
        return None
    con_ancho = [c for c in candidatos if c[0] is not None]
    if con_ancho:
        return max(con_ancho, key=lambda c: c[0])[1]
    return candidatos[0][1]


def _is_placeholder(url: str) -> bool:
    lower = url.lower()
    if lower.startswith("data:") or "base64" in lower or "1x1" in lower:
        return True
    return bool(_PLACEHOLDER_RE.search(lower))
