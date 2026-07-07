"""Cliente Supabase y funciones de acceso a datos."""
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


def touch_listing(listing_id: str, seen_at: str) -> None:
    (
        get_client()
        .table("listings")
        .update({"last_seen_available_at": seen_at})
        .eq("id", listing_id)
        .execute()
    )
