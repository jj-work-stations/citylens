# # app/apis/v1/tracking/location_history.py

from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import AllowedCityIds, TenantAdminUser
from app.core.exceptions import AppError
from app.schemas.tracking.location_history import (
    LocationHistoryFilter,
    LocationStatsResponse,
    PaginatedLocationHistory,
)
from app.services.tracking.location_history import LocationHistoryService
import logging

router = APIRouter(
    prefix="/tracking/location-history",
    tags=["Tracking - Location History"],
)

MARTIN_BASE = "http://martin:3000"



logger = logging.getLogger(__name__)


def _svc(db: AsyncSession = Depends(get_db)) -> LocationHistoryService:
    return LocationHistoryService(db)


def _parse_filters(
    gender:         Optional[str]      = Query(None, description="M or F"),
    age_min:        Optional[int]      = Query(None, ge=0, le=120),
    age_max:        Optional[int]      = Query(None, ge=0, le=120),
    city_id:        Optional[int]      = Query(None, description="City ID"),
    timestamp_from: Optional[datetime] = Query(None),
    timestamp_to:   Optional[datetime] = Query(None),
    bbox:           Optional[str]      = Query(None, description="xmin,ymin,xmax,ymax"),
) -> LocationHistoryFilter:
    return LocationHistoryFilter(
        gender         = gender,
        age_min        = age_min,
        age_max        = age_max,
        city_id        = city_id,
        timestamp_from = timestamp_from,
        timestamp_to   = timestamp_to,
        bbox           = bbox,
    )


def _scoped(
    filters:          LocationHistoryFilter = Depends(_parse_filters),
    allowed_city_ids: AllowedCityIds        = None,
) -> LocationHistoryFilter:
    """
    Merge the security scope into the filter object.
    This is the single place where city access control is applied.

    allowed_city_ids=None   → admin, no restriction
    allowed_city_ids=[1,2]  → tenant_admin, restrict to these cities
    allowed_city_ids=[]     → tenant_admin with no cities → empty result
    """
    filters.allowed_city_ids = allowed_city_ids
    return filters


@router.get("", response_model=PaginatedLocationHistory)
async def list_location_history(
    _:         TenantAdminUser,                          # auth guard
    filters:   LocationHistoryFilter = Depends(_scoped),
    svc:       LocationHistoryService = Depends(_svc),
    page:      int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=5000),
):
    try:
        return await svc.list_records(filters, page, page_size)
    except AppError as e:
        raise e.to_http()


@router.get("/stats", response_model=LocationStatsResponse)
async def get_stats(
    _:       TenantAdminUser,
    filters: LocationHistoryFilter  = Depends(_scoped),
    svc:     LocationHistoryService = Depends(_svc),
):
    try:
        return await svc.get_stats(filters)
    except AppError as e:
        raise e.to_http()









# from app.core.dependencies import AllowedCityIds, TenantAdminUser
# from app.services.tile_cache import get_cached_tile, set_cached_tile


# # ── Constants ──────────────────────────────────────────────────
# TILE_CACHE_TTL_SECONDS = 172_800       # 2 days
# CACHE_PUBLIC_MAX_AGE  = 172_800         # 2 days, tells browsers/CDNs




# @router.get("/tiles/{z}/{x}/{y}")
# async def get_tile(
#     z: int,
#     x: int,
#     y: int,
#     _:       TenantAdminUser,
#     allowed_city_ids: AllowedCityIds,
#     filters: LocationHistoryFilter = Depends(_scoped),
# ):

#     # ── Auth scope ────────────────────────────────────────────────
#     if not _.has_city_access(filters.city_id):
#         return Response(status_code=204)

#     # ── Build Martin query params ────────────────────────────────
#     params: dict = {}

#     if filters.gender:
#         params["gender"] = filters.gender
#     if filters.age_min is not None:
#         params["age_min"] = str(filters.age_min)
#     if filters.age_max is not None:
#         params["age_max"] = str(filters.age_max)
#     if filters.timestamp_from:
#         params["timestamp_from"] = filters.timestamp_from.isoformat()
#     if filters.timestamp_to:
#         params["timestamp_to"] = filters.timestamp_to.isoformat()
#     if filters.bbox:
#         params["bbox"] = filters.bbox

#     # City scoping
#     if filters.allowed_city_ids is not None:
#         params["city_ids"] = ",".join(str(c) for c in filters.allowed_city_ids)
#     elif filters.city_id is not None:
#         params["city_id"] = str(filters.city_id)

#     cached = await get_cached_tile(z, x, y, params)
#     if cached is not None:
#         return Response(
#             content=cached,
#             media_type="application/vnd.mapbox-vector-tile",
#             headers={
#                 "Cache-Control": f"public, max-age={CACHE_PUBLIC_MAX_AGE}",
#                 "X-Cache": "HIT",
#             },
#         )

#     url = f"{MARTIN_BASE}/tile_location_history/{z}/{x}/{y}"

#     async with httpx.AsyncClient(timeout=15) as client:
#         try:
#             resp = await client.get(url, params=params)
#         except httpx.RequestError as exc:
#             logger.error("TILE Martin request error: %s", exc)
#             return Response(status_code=502, content=str(exc).encode())

#     # ── Handle empty / error from Martin ────────────────────────
#     if not resp.content or resp.status_code == 204:
#         return Response(status_code=204)

#     mvt_data = resp.content

#     await set_cached_tile(z, x, y, params, mvt_data, TILE_CACHE_TTL_SECONDS)

#     return Response(
#         content=mvt_data,
#         media_type="application/vnd.mapbox-vector-tile",
#         headers={
#             "Cache-Control": f"public, max-age={CACHE_PUBLIC_MAX_AGE}",
#             "X-Cache": "MISS",
#             # Optional: tell CDNs / proxies this can be cached per URL+params
#             "Vary":          "Accept-Encoding",
#         },
#     )








import gzip
import hashlib
import json
from app.services.tile_cache import get_cached_tile, set_cached_tile


TILE_CACHE_TTL_SECONDS  = 172_800   # 2 days Redis TTL
HTTP_CACHE_MAX_AGE      = 172_800   # 2 days browser/CDN TTL
MVT_CONTENT_TYPE        = "application/vnd.mapbox-vector-tile"


def _parse_filters(
    gender:         Optional[str]      = Query(None),
    age_min:        Optional[int]      = Query(None, ge=0, le=120),
    age_max:        Optional[int]      = Query(None, ge=0, le=120),
    city_id:        Optional[int]      = Query(None),
    timestamp_from: Optional[datetime] = Query(None),
    timestamp_to:   Optional[datetime] = Query(None),
    bbox:           Optional[str]      = Query(None),
) -> LocationHistoryFilter:
    return LocationHistoryFilter(
        gender=gender, age_min=age_min, age_max=age_max,
        city_id=city_id, timestamp_from=timestamp_from,
        timestamp_to=timestamp_to, bbox=bbox,
    )


def _scoped(
    filters:          LocationHistoryFilter = Depends(_parse_filters),
    allowed_city_ids: AllowedCityIds        = None,
) -> LocationHistoryFilter:
    filters.allowed_city_ids = allowed_city_ids
    return filters


# ── helpers ────────────────────────────────────────────────────────────────────

def _compress(data: bytes) -> bytes:
    """Gzip compress bytes at level 6 (good balance speed/size)."""
    return gzip.compress(data, compresslevel=6)


def _build_martin_params(filters: LocationHistoryFilter) -> dict:
    """Convert filter object → Martin query-string dict."""
    params: dict = {}
    if filters.gender:
        params["gender"] = filters.gender
    if filters.age_min is not None:
        params["age_min"] = str(filters.age_min)
    if filters.age_max is not None:
        params["age_max"] = str(filters.age_max)

    if filters.timestamp_from:
        params["timestamp_from"] = filters.timestamp_from.isoformat()
    if filters.timestamp_to:
        params["timestamp_to"] = filters.timestamp_to.isoformat()

    if filters.bbox:
        params["bbox"] = filters.bbox

    if filters.allowed_city_ids is not None:
        params["city_ids"] = ",".join(str(c) for c in filters.allowed_city_ids)
    elif filters.city_id is not None:
        params["city_id"] = str(filters.city_id)

    return params


def _tile_response(
    content: bytes,
    *,
    cache_hit: bool,
    original_size: Optional[int] = None,
) -> Response:
    """
    Return a gzip-compressed MVT response with correct headers.
    Content must already be gzip-compressed before calling this.
    """
    headers = {
        # ── Caching ───────────────────────────────────────────
        "Cache-Control": f"public, max-age={HTTP_CACHE_MAX_AGE}",
        "Vary":          "Accept-Encoding",

        # ── Compression ───────────────────────────────────────
        "Content-Encoding": "gzip",

        # ── Debug ─────────────────────────────────────────────
        "X-Cache": "HIT" if cache_hit else "MISS",
    }

    if original_size is not None:
        headers["X-Tile-Bytes-Raw"]        = str(original_size)
        headers["X-Tile-Bytes-Compressed"] = str(len(content))
        ratio = round(len(content) / original_size * 100, 1)
        headers["X-Tile-Compression-Ratio"] = f"{ratio}%"

    return Response(
        content=content,
        media_type=MVT_CONTENT_TYPE,
        headers=headers,
    )


# ── endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedLocationHistory)
async def list_location_history(
    _:         TenantAdminUser,
    filters:   LocationHistoryFilter  = Depends(_scoped),
    svc:       LocationHistoryService = Depends(_svc),
    page:      int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=5000),
):
    try:
        return await svc.list_records(filters, page, page_size)
    except AppError as e:
        raise e.to_http()


@router.get("/stats", response_model=LocationStatsResponse)
async def get_stats(
    _:       TenantAdminUser,
    filters: LocationHistoryFilter  = Depends(_scoped),
    svc:     LocationHistoryService = Depends(_svc),
):
    try:
        return await svc.get_stats(filters)
    except AppError as e:
        raise e.to_http()


@router.get("/tiles/{z}/{x}/{y}")
async def get_tile(
    z: int,
    x: int,
    y: int,
    _:                TenantAdminUser,
    allowed_city_ids: AllowedCityIds,
    filters:          LocationHistoryFilter = Depends(_scoped),
):
    """
    Serve MapLibre MVT tile.

    Pipeline:
      1. Auth city scope check
      2. Redis cache lookup  → return compressed bytes immediately (HIT)
      3. Martin fetch        → compress → store in Redis → return (MISS)

    Response is always gzip-compressed so Content-Encoding: gzip is set.
    MapLibre handles decompression automatically.
    """

    # ── 0. Auth: tenant_admin with no cities → empty ──────────
    if not _.has_city_access(filters.city_id):
        return Response(status_code=204)

    if filters.allowed_city_ids is not None and len(filters.allowed_city_ids) == 0:
        return Response(status_code=204)

    # ── 1. Build Martin params ─────────────────────────────────
    params = _build_martin_params(filters)

    logger.debug("TILE z=%s x=%s y=%s params=%s", z, x, y, params)

    # ── 2. Redis cache lookup (stores compressed bytes) ────────
    cached = await get_cached_tile(z, x, y, params)
    if cached is not None:
        logger.debug("TILE CACHE HIT z=%s x=%s y=%s", z, x, y)
        return _tile_response(cached, cache_hit=True)

    # ── 3. Fetch from Martin ───────────────────────────────────
    url = f"{MARTIN_BASE}/tile_location_history/{z}/{x}/{y}"

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(url, params=params)
        except httpx.RequestError as exc:
            logger.error("Martin unreachable: %s", exc)
            return Response(status_code=502, content=b"tile service unavailable")

    if not resp.content or resp.status_code == 204:
        logger.debug("TILE EMPTY z=%s x=%s y=%s", z, x, y)
        return Response(status_code=204)

    raw_bytes     = resp.content
    original_size = len(raw_bytes)

    # ── 4. Compress ────────────────────────────────────────────
    compressed = _compress(raw_bytes)

    logger.info(
        "TILE MISS z=%s x=%s y=%s | raw=%s compressed=%s ratio=%.1f%%",
        z, x, y,
        original_size,
        len(compressed),
        len(compressed) / original_size * 100,
    )

    # ── 5. Store COMPRESSED bytes in Redis ────────────────────
    #       so HIT path never needs to compress again
    await set_cached_tile(z, x, y, params, compressed, TILE_CACHE_TTL_SECONDS)

    # ── 6. Return compressed response ─────────────────────────
    return _tile_response(
        compressed,
        cache_hit=False,
        original_size=original_size,
    )