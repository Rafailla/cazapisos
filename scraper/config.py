"""Carga de configuración desde variables de entorno (.env en local)."""
import os

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")


def validate() -> None:
    faltantes = [
        nombre
        for nombre, valor in (("SUPABASE_URL", SUPABASE_URL), ("SUPABASE_KEY", SUPABASE_KEY))
        if not valor
    ]
    if faltantes:
        raise RuntimeError(
            f"Faltan variables de entorno: {', '.join(faltantes)}. "
            "Copia .env.example a .env y rellénalo."
        )
