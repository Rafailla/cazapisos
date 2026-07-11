"""Cliente Supabase y funciones de acceso a datos."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from supabase import Client, create_client

import config


@lru_cache(maxsize=1)
def get_client() -> Client:
    config.validate()
    return create_client(config.SUPABASE_URL, config.SUPABASE_KEY)


def get_active_platforms() -> list[dict]:
    response = get_client().table("platforms").select("*").eq("active", True).execute()
    return response.data


def get_active_filters() -> list[dict]:
    response = get_client().table("filters").select("*").eq("active", True).execute()
    return response.data


def get_active_recipients(type: str) -> list[dict]:
    response = (
        get_client()
        .table("recipients")
        .select("*")
        .eq("active", True)
        .eq("type", type)
        .execute()
    )
    return response.data


def get_active_recipients_by_group(group_id: str, type: str) -> list[dict]:
    response = (
        get_client()
        .table("recipients")
        .select("*")
        .eq("active", True)
        .eq("type", type)
        .eq("group_id", group_id)
        .execute()
    )
    return response.data


def get_groups() -> list[dict]:
    response = get_client().table("groups").select("*").execute()
    return response.data


def find_listing(platform_id: str, dedup_hash: str) -> dict | None:
    response = (
        get_client()
        .table("listings")
        .select("id")
        .eq("platform_id", platform_id)
        .eq("dedup_hash", dedup_hash)
        .execute()
    )
    return response.data[0] if response.data else None


def insert_listing(row: dict) -> None:
    get_client().table("listings").insert(row).execute()


def touch_listing(listing_id: str, seen_at: str, has_pool: bool, condition: str | None) -> None:
    (
        get_client()
        .table("listings")
        .update({"last_seen_available_at": seen_at, "has_pool": has_pool, "condition": condition})
        .eq("id", listing_id)
        .execute()
    )


def get_available_listings() -> list[dict]:
    """Todos los listings disponibles, con el nombre de la plataforma ya
    incluido (aplanado desde el join), ordenados por fecha de primera
    detección descendente."""
    response = (
        get_client()
        .table("listings")
        .select("*, platforms(name)")
        .eq("available", True)
        .order("first_seen_at", desc=True)
        .execute()
    )
    listings = []
    for row in response.data:
        platform = row.pop("platforms", None) or {}
        row["platform_name"] = platform.get("name")
        listings.append(row)
    return listings


def update_platform_last_new_listing(platform_id: str) -> None:
    (
        get_client()
        .table("platforms")
        .update({"last_new_listing_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", platform_id)
        .execute()
    )


def update_platform_check_result(platform_id: str, new_count: int) -> None:
    (
        get_client()
        .table("platforms")
        .update(
            {
                "last_checked_at": datetime.now(timezone.utc).isoformat(),
                "last_run_new_count": new_count,
            }
        )
        .eq("id", platform_id)
        .execute()
    )


def get_stale_platforms(days: int = 5) -> list[dict]:
    """Plataformas activas sin ningún anuncio nuevo desde hace `days` días
    (o, si nunca han aportado ninguno, creadas hace más de `days` días)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stale = []
    for platform in get_active_platforms():
        reference = platform.get("last_new_listing_at") or platform.get("created_at")
        if reference is None:
            continue
        if datetime.fromisoformat(reference) < cutoff:
            stale.append(platform)
    return stale


def log_execution(trigger_type: str, new_listings_count: int, status: str, notes: str | None = None) -> None:
    get_client().table("execution_log").insert(
        {
            "trigger_type": trigger_type,
            "new_listings_count": new_listings_count,
            "status": status,
            "notes": notes,
        }
    ).execute()
