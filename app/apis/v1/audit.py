# app/apis/v1/audit.py
import json
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.core.dependencies import AdminUser
from app.schemas.audit import AuditLogResponse
from app.schemas.base import PaginatedResponse

router = APIRouter(prefix="/audit", tags=["Audit"])

LOKI_URL       = "http://loki:3100"
LOKI_QUERY_URL = f"{LOKI_URL}/loki/api/v1/query_range"

DEFAULT_LOOKBACK_DAYS = 7
LOKI_MAX_LINES        = 5_000   # max lines fetched per query window


def _build_logql(
    user_id:       Optional[str],
    action:        Optional[str],
    resource_type: Optional[str],
    status_code:   Optional[int],
) -> str:
    base = '{app="citylens", service="api", type="audit"} | json'

    filters: list[str] = []
    if user_id:
        filters.append(f'user_id="{user_id}"')
    if action:
        filters.append(f'action="{action}"')
    if resource_type:
        filters.append(f'resource_type="{resource_type}"')
    if status_code is not None:
        filters.append(f'status_code="{status_code}"')

    return base + (" | " + " | ".join(filters) if filters else "")


def _time_range_ns(
    date_from: Optional[datetime],
    date_to:   Optional[datetime],
) -> tuple[int, int]:
    now   = datetime.now(timezone.utc)
    start = date_from or datetime.fromtimestamp(
        now.timestamp() - DEFAULT_LOOKBACK_DAYS * 86_400,
        tz=timezone.utc,
    )
    end = date_to or now
    return int(start.timestamp() * 1e9), int(end.timestamp() * 1e9)


def _parse_loki_response(result: list) -> list[dict]:
    entries: list[dict] = []

    for stream in result:
        for ts_ns_str, line in stream.get("values", []):
            try:
                ts_ns = int(ts_ns_str)
                entry = json.loads(line)
                entry["created_at"] = datetime.fromtimestamp(
                    ts_ns / 1e9, tz=timezone.utc
                ).isoformat()
                entry["_ts_ns"] = ts_ns
                entries.append(entry)
            except Exception:
                continue

    entries.sort(key=lambda e: e["_ts_ns"], reverse=True)

    for e in entries:
        e.pop("_ts_ns", None)

    return entries


async def _fetch_loki(
    logql:    str,
    start_ns: int,
    end_ns:   int,
    limit:    int,
) -> list:
    """Single Loki HTTP call. Returns raw result list."""
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.get(
                LOKI_QUERY_URL,
                params={
                    "query":     logql,
                    "start":     str(start_ns),
                    "end":       str(end_ns),
                    "limit":     str(limit),
                    "direction": "backward",
                },
            )
            resp.raise_for_status()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Loki query timed out")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Loki error {exc.response.status_code}: {exc.response.text[:300]}",
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Loki unreachable: {exc}")

    return resp.json().get("data", {}).get("result", [])


@router.get("", response_model=PaginatedResponse[AuditLogResponse])
async def get_audit_logs(
    _:             AdminUser,
    page:          int = Query(1,   ge=1),
    page_size:     int = Query(50,  ge=1, le=200),
    user_id:       Optional[str]      = Query(None),
    action:        Optional[str]      = Query(None),
    resource_type: Optional[str]      = Query(None),
    status_code:   Optional[int]      = Query(None),
    date_from:     Optional[datetime] = Query(None),
    date_to:       Optional[datetime] = Query(None),
):
    """
    Query audit logs from Loki.

    Always fetches LOKI_MAX_LINES (5000) so `total` reflects
    the real count — not just the current page size.
    Pagination is done in-memory after fetching.
    """
    logql            = _build_logql(user_id, action, resource_type, status_code)
    start_ns, end_ns = _time_range_ns(date_from, date_to)

    # ── Always fetch the max so we know the real total ─────────
    result   = await _fetch_loki(logql, start_ns, end_ns, limit=LOKI_MAX_LINES)
    all_logs = _parse_loki_response(result)

    total  = len(all_logs)
    offset = (page - 1) * page_size
    paged  = all_logs[offset : offset + page_size]

    return PaginatedResponse.build(paged, total, page, page_size)