# # app/services/tile_cache.py
# import hashlib
# import json
# import logging
# from typing import Optional

# import redis.asyncio as aioredis
# from app.core.config import settings

# logger = logging.getLogger(__name__)

# # Single Redis connection for tile caching
# _redis: Optional[aioredis.Redis] = None


# async def get_tile_cache() -> aioredis.Redis:
#     """Lazy-init shared Redis connection for tile caching."""
#     global _redis
#     if _redis is None:
#         _redis = await aioredis.from_url(
#             settings.REDIS_URL,
#             decode_responses=False,   # bytes — we store raw MVT binary
#         )
#     return _redis


# def _make_cache_key(z: int, x: int, y: int, params: dict) -> str:
#     """
#     Build deterministic cache key from tile coords + sorted params.
    
#     Example: tile:10:660/402:city_id=1|ts_from=2026-06-10T00:00:00Z
#     """
#     # Sort params so same filters in any order → same key
#     canonical = json.dumps(params, sort_keys=True, default=str)
#     hash_id = hashlib.sha256(canonical.encode()).hexdigest()[:16]
#     return f"tile:{z}:{x}/{y}:{hash_id}"


# async def get_cached_tile(
#     z: int,
#     x: int,
#     y: int,
#     params: dict,
# ) -> Optional[bytes]:
#     """Return cached MVT bytes or None."""
#     try:
#         rc = await get_tile_cache()
#         key = _make_cache_key(z, x, y, params)
#         data = await rc.get(key)
#         if data is not None:
#             logger.debug("TILE CACHE HIT: %s", key)
#         return data
#     except Exception as exc:
#         logger.warning("Tile cache get failed (serving fresh): %s", exc)
#         return None


# async def set_cached_tile(
#     z: int,
#     x: int,
#     y: int,
#     params: dict,
#     data: bytes,
#     ttl_sec: int = 172_800,     # ← 2 days in seconds = 172800
# ) -> None:
#     """Store MVT bytes in Redis with expiration."""
#     if not data:
#         return   # never cache empty responses
#     try:
#         rc = await get_tile_cache()
#         key = _make_cache_key(z, x, y, params)
#         await rc.setex(key, ttl_sec, data)
#         logger.debug("TILE CACHE SET: %s (ttl=%ss)", key, ttl_sec)
#     except Exception as exc:
#         logger.warning("Tile cache set failed: %s", exc)


# async def invalidate_city_tiles(city_ids: list[int]) -> int:
#     """
#     Call this when city assignments change.
#     Returns number of keys deleted.
#     """
#     try:
#         rc = await get_tile_cache()
#         pattern = "tile:*"
#         cursor = b"0"
#         deleted = 0
#         while True:
#             cursor, keys = await rc.scan(cursor, match=pattern, count=1000)
#             if keys:
#                 n = await rc.delete(*keys)
#                 deleted += n
#             if cursor == b"0":
#                 break
#         logger.info("Invalidated %d tile cache entries", deleted)
#         return deleted
#     except Exception as exc:
#         logger.error("Cache invalidation error: %s", exc)
#         return 0



# app/services/tile_cache.py
import hashlib
from typing import Optional

import redis.asyncio as redis

from app.core.redis import redis_client


def _tile_cache_key(z: int, x: int, y: int, params: dict, version: str = "v1") -> str:
    """
    Build a stable cache key for this tile + filters.
    """
    # Sort params so order doesn't break the cache
    sorted_params = sorted(params.items())
    
    # Build a deterministic string
    param_string = "&".join(f"{k}={v}" for k, v in sorted_params)
    
    raw_key = f"tile:location-history:{version}:{z}:{x}:{y}:{param_string}"
    
    # Hash it so keys are short and safe
    digest = hashlib.sha256(raw_key.encode()).hexdigest()
    return f"tile:lh:{version}:{digest}"


async def get_cached_tile(
    z: int, 
    x: int, 
    y: int, 
    params: dict,
    version: str = "v1",
) -> Optional[bytes]:
    """
    Returns compressed tile bytes if cached. Otherwise None.
    """
    key = _tile_cache_key(z, x, y, params, version)
    cached = await redis_client.get(key)
    
    if cached is None:
        return None
    
    return cached  # This is the gzip-compressed MVT bytes


async def set_cached_tile(
    z: int,
    x: int,
    y: int,
    params: dict,
    compressed_mvt: bytes,
    ttl_seconds: int,
    version: str = "v1",
) -> None:
    """
    Store gzip-compressed tile bytes in Redis.
    """
    key = _tile_cache_key(z, x, y, params, version)
    await redis_client.set(key, compressed_mvt, ex=ttl_seconds)