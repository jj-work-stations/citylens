# app/core/loki.py
import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

LOKI_URL        = os.getenv("LOKI_URL", "http://loki:3100")
LOKI_PUSH_URL   = f"{LOKI_URL}/loki/api/v1/push"
LOKI_STREAM_LABELS = '{app="citylens", service="api", type="audit"}'

# Shared async client — reused across all pushes
_client: httpx.AsyncClient | None = None


def get_loki_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=2.0, read=5.0, write=5.0, pool=2.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        logger.info("Loki HTTP client created → %s", LOKI_PUSH_URL)
    return _client


async def close_loki_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.info("Loki HTTP client closed")


async def push_logs_to_loki(entries: list[tuple[str, str]]) -> None:
    """
    Push a batch of log entries to Loki.

    entries: list of (nanosecond_timestamp_str, log_line_str)
    """
    if not entries:
        return

    payload = {
        "streams": [
            {
                "stream": {
                    "app":     "citylens",
                    "service": "api",
                    "type":    "audit",
                },
                "values": entries,   # [["<nanoseconds>", "<log line>"], ...]
            }
        ]
    }

    try:
        client = get_loki_client()
        resp = await client.post(LOKI_PUSH_URL, json=payload)
        if resp.status_code not in (200, 204):
            logger.warning(
                "Loki push returned %s: %s",
                resp.status_code,
                resp.text[:200],
            )
    except Exception as exc:
        logger.error("Loki push failed: %s", exc, exc_info=False)