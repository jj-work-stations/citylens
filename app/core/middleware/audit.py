# # app/core/middleware/audit.py
# import json
# import logging
# import re
# import time
# from dataclasses import dataclass
# from typing import Optional

# from starlette.middleware.base import BaseHTTPMiddleware
# from starlette.requests import Request
# from starlette.responses import Response

# from app.core.database import AsyncSessionLocal
# from app.models.audit import AuditLog

# logger = logging.getLogger(__name__)

# SKIP_PATHS = {
#     "/health",
#     "/docs",
#     "/redoc",
#     "/openapi.json",
#     "/favicon.ico",
# }

# SENSITIVE_FIELDS = {"password", "hashed_password", "token", "refresh_token"}

# PATH_RULES: list[tuple[re.Pattern, str, str]] = [
#     (re.compile(r"^/api/v1/auth/login"),   "LOGIN",         "auth"),
#     (re.compile(r"^/api/v1/auth/logout"),  "LOGOUT",        "auth"),
#     (re.compile(r"^/api/v1/auth/refresh"), "REFRESH_TOKEN", "auth"),
#     (re.compile(r"^/api/v1/users"),        "USER",          "user"),
#     (re.compile(r"^/api/v1/provinces"),    "PROVINCE",      "province"),
#     (re.compile(r"^/api/v1/services"),     "SERVICE",       "service"),
#     (re.compile(r"^/api/v1/map"),          "MAP",           "map"),
#     (re.compile(r"^/api/v1/audit"),        "AUDIT",         "audit"),
# ]

# METHOD_MAP = {
#     "GET":    "READ",
#     "POST":   "CREATE",
#     "PUT":    "UPDATE",
#     "PATCH":  "PARTIAL_UPDATE",
#     "DELETE": "DELETE",
# }

# _UUID_RE = re.compile(
#     r"/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
#     re.IGNORECASE,
# )


# # ── Plain dataclass — NO SQLAlchemy, NO session needed ────────
# @dataclass
# class UserSnapshot:
#     """
#     Stores only primitive values copied from the User ORM object
#     while the DB session is still open.
#     After this snapshot is created, we never touch the ORM object again.
#     """
#     id: str
#     role: str
#     phone: str


# def _classify(method: str, path: str) -> tuple[str, str]:
#     for pattern, resource, rtype in PATH_RULES:
#         if pattern.match(path):
#             return f"{METHOD_MAP.get(method, method)}_{resource}", rtype
#     return METHOD_MAP.get(method, "UNKNOWN"), "unknown"


# def _mask(data: Optional[dict]) -> Optional[dict]:
#     if not data:
#         return data
#     return {
#         k: "***" if k.lower() in SENSITIVE_FIELDS else v
#         for k, v in data.items()
#     }


# def _extract_id(path: str) -> Optional[str]:
#     m = _UUID_RE.search(path)
#     return m.group(1) if m else None


# def _get_client_ip(request: Request) -> Optional[str]:
#     forwarded = request.headers.get("X-Forwarded-For")
#     if forwarded:
#         return forwarded.split(",")[0].strip()
#     return request.client.host if request.client else None


# class AuditMiddleware(BaseHTTPMiddleware):

#     async def dispatch(self, request: Request, call_next) -> Response:
#         if request.url.path in SKIP_PATHS:
#             return await call_next(request)

#         start = time.monotonic()
#         body  = await self._read_body(request)

#         # ── Run the actual route ───────────────────────────────
#         response = await call_next(request)

#         elapsed = int((time.monotonic() - start) * 1000)

#         # ── Snapshot user data NOW (session may close after this) 
#         user_snapshot = self._snapshot_user(request)

#         # ── Write audit log with plain values only ─────────────
#         await self._write_log(
#             request=request,
#             status_code=response.status_code,
#             elapsed=elapsed,
#             body=body,
#             user_snapshot=user_snapshot,
#         )

#         return response

#     # ── Helpers ────────────────────────────────────────────────

#     def _snapshot_user(self, request: Request) -> Optional[UserSnapshot]:
#         """
#         Copy primitive values out of the ORM User object
#         while we are still inside the request context (session open).
#         Returns a plain dataclass — safe to use after session closes.
#         """
#         user = getattr(request.state, "current_user", None)
#         if user is None:
#             return None

#         try:
#             # Access all attributes HERE while session is still alive
#             return UserSnapshot(
#                 id=str(user.id),
#                 role=str(user.role),
#                 phone=str(user.phone),
#             )
#         except Exception as exc:
#             # If for any reason the user object is already detached,
#             # log a warning but do NOT crash the request
#             logger.warning("Could not snapshot user for audit log: %s", exc)
#             return None

#     async def _read_body(self, request: Request) -> Optional[dict]:
#         if request.method not in ("POST", "PUT", "PATCH"):
#             return None
#         try:
#             raw = await request.body()
#             return _mask(json.loads(raw)) if raw else None
#         except Exception:
#             return None

#     async def _write_log(
#         self,
#         request: Request,
#         status_code: int,
#         elapsed: int,
#         body: Optional[dict],
#         user_snapshot: Optional[UserSnapshot],
#     ) -> None:
#         action, resource_type = _classify(request.method, request.url.path)

#         entry = AuditLog(
#             # ── Use snapshot values (plain strings) ───────────
#             user_id    = user_snapshot.id    if user_snapshot else None,
#             user_role  = user_snapshot.role  if user_snapshot else None,
#             user_phone = user_snapshot.phone if user_snapshot else None,

#             # ── Request ───────────────────────────────────────
#             method       = request.method,
#             path         = request.url.path,
#             query_params = dict(request.query_params) or None,
#             request_body = body,

#             # ── Response ──────────────────────────────────────
#             status_code     = status_code,
#             response_time_ms = elapsed,

#             # ── Classification ────────────────────────────────
#             action        = action,
#             resource_type = resource_type,
#             resource_id   = _extract_id(request.url.path),

#             # ── Client ────────────────────────────────────────
#             ip_address = _get_client_ip(request),
#             user_agent = request.headers.get("user-agent"),
#         )

#         try:
#             async with AsyncSessionLocal() as session:
#                 session.add(entry)
#                 await session.commit()
#         except Exception as exc:
#             # Never crash the response because of audit failure
#             logger.error("Audit log write failed: %s", exc)
























# # app/core/middleware/audit.py
# import asyncio
# import json
# import logging
# import re
# import time
# from dataclasses import asdict, dataclass
# from datetime import datetime, timezone
# from typing import Optional

# from starlette.types import ASGIApp, Receive, Scope, Send

# from app.core.loki import push_logs_to_loki

# logger = logging.getLogger(__name__)

# # ── Config ─────────────────────────────────────────────────────
# QUEUE_MAX_SIZE = 10_000
# BATCH_SIZE     = 100
# BATCH_TIMEOUT  = 2.0      # seconds — flush even if batch not full
# WORKER_COUNT   = 2

# SKIP_PATHS = frozenset({
#     "/health",
#     "/docs",
#     "/redoc",
#     "/openapi.json",
#     "/favicon.ico",
# })

# SKIP_PREFIXES = (
#     "/api/v1/tracking/location-history/tiles",
# )

# SENSITIVE_FIELDS = frozenset({
#     "password", "hashed_password", "token", "refresh_token",
# })

# PATH_RULES: list[tuple[re.Pattern, str, str]] = [
#     (re.compile(r"^/api/v1/auth/login"),   "LOGIN",         "auth"),
#     (re.compile(r"^/api/v1/auth/logout"),  "LOGOUT",        "auth"),
#     (re.compile(r"^/api/v1/auth/refresh"), "REFRESH_TOKEN", "auth"),
#     (re.compile(r"^/api/v1/users"),        "USER",          "user"),
#     (re.compile(r"^/api/v1/provinces"),    "PROVINCE",      "province"),
#     (re.compile(r"^/api/v1/services"),     "SERVICE",       "service"),
#     (re.compile(r"^/api/v1/map"),          "MAP",           "map"),
#     (re.compile(r"^/api/v1/audit"),        "AUDIT",         "audit"),
#     (re.compile(r"^/api/v1/tracking"),     "TRACKING",      "tracking"),
# ]

# METHOD_MAP = {
#     "GET":    "READ",
#     "POST":   "CREATE",
#     "PUT":    "UPDATE",
#     "PATCH":  "PARTIAL_UPDATE",
#     "DELETE": "DELETE",
# }

# _UUID_RE = re.compile(
#     r"/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
#     re.IGNORECASE,
# )


# # ── Entry ──────────────────────────────────────────────────────

# @dataclass(slots=True)
# class AuditEntry:
#     user_id:          Optional[str]
#     user_role:        Optional[str]
#     user_phone:       Optional[str]
#     method:           str
#     path:             str
#     query_params:     Optional[dict]
#     request_body:     Optional[dict]
#     status_code:      int
#     response_time_ms: int
#     action:           str
#     resource_type:    str
#     resource_id:      Optional[str]
#     ip_address:       Optional[str]
#     user_agent:       Optional[str]
#     ts_ns:            str    # nanosecond timestamp string for Loki


# # ── Queue + workers ────────────────────────────────────────────

# _queue: asyncio.Queue[AuditEntry] = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
# _workers: list[asyncio.Task] = []


# async def _batch_writer() -> None:
#     """
#     Drains queue, converts entries to Loki log lines, pushes in batches.
#     One HTTP POST to Loki per batch — very efficient.
#     """
#     while True:
#         batch: list[AuditEntry] = []

#         # Wait for first item
#         try:
#             entry = await asyncio.wait_for(_queue.get(), timeout=BATCH_TIMEOUT)
#             batch.append(entry)
#         except asyncio.TimeoutError:
#             continue

#         # Drain more without blocking
#         while len(batch) < BATCH_SIZE:
#             try:
#                 batch.append(_queue.get_nowait())
#             except asyncio.QueueEmpty:
#                 break

#         if not batch:
#             continue

#         # Convert to Loki format: [["<ns_timestamp>", "<json_log_line>"], ...]
#         loki_entries: list[tuple[str, str]] = []
#         for e in batch:
#             log_line = json.dumps(
#                 {
#                     "user_id":          e.user_id,
#                     "user_role":        e.user_role,
#                     "user_phone":       e.user_phone,
#                     "method":           e.method,
#                     "path":             e.path,
#                     "query_params":     e.query_params,
#                     "request_body":     e.request_body,
#                     "status_code":      e.status_code,
#                     "response_time_ms": e.response_time_ms,
#                     "action":           e.action,
#                     "resource_type":    e.resource_type,
#                     "resource_id":      e.resource_id,
#                     "ip_address":       e.ip_address,
#                     "user_agent":       e.user_agent,
#                 },
#                 ensure_ascii=False,
#                 default=str,
#             )
#             loki_entries.append((e.ts_ns, log_line))

#         # Push whole batch in one HTTP call
#         await push_logs_to_loki(loki_entries)

#         logger.debug("Audit: pushed %d entries to Loki", len(loki_entries))

#         for _ in batch:
#             _queue.task_done()


# def start_audit_workers() -> None:
#     global _workers
#     _workers = [
#         asyncio.create_task(_batch_writer(), name=f"audit-loki-writer-{i}")
#         for i in range(WORKER_COUNT)
#     ]
#     logger.info("Audit: %d Loki writer workers started", WORKER_COUNT)


# async def stop_audit_workers() -> None:
#     """Flush remaining entries then cancel workers."""
#     try:
#         await asyncio.wait_for(_queue.join(), timeout=10.0)
#     except asyncio.TimeoutError:
#         logger.warning("Audit: queue not fully flushed on shutdown")
#     for task in _workers:
#         task.cancel()
#         try:
#             await task
#         except asyncio.CancelledError:
#             pass
#     logger.info("Audit: Loki workers stopped")


# # ── Pure ASGI middleware ────────────────────────────────────────

# class AuditMiddleware:

#     def __init__(self, app: ASGIApp) -> None:
#         self.app = app

#     async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
#         if scope["type"] != "http":
#             await self.app(scope, receive, send)
#             return

#         path   = scope.get("path", "")
#         method = scope.get("method", "GET")

#         if path in SKIP_PATHS or path.startswith(SKIP_PREFIXES):
#             await self.app(scope, receive, send)
#             return

#         start      = time.monotonic()
#         body_bytes = b""

#         if method in ("POST", "PUT", "PATCH"):
#             body_bytes = await _read_body(receive)
#             receive    = _replay_receive(body_bytes)

#         status_code = 500

#         async def send_wrapper(message) -> None:
#             nonlocal status_code
#             if message["type"] == "http.response.start":
#                 status_code = message["status"]
#             await send(message)

#         await self.app(scope, receive, send_wrapper)

#         elapsed = int((time.monotonic() - start) * 1000)

#         # Nanosecond timestamp for Loki (must be string)
#         ts_ns = str(time.time_ns())

#         # User snapshot from scope state
#         user_id = user_role = user_phone = None
#         state = scope.get("state")
#         if state is not None:
#             u = getattr(state, "current_user", None)
#             if u is not None:
#                 try:
#                     user_id    = str(u.id)
#                     user_role  = str(u.role)
#                     user_phone = str(u.phone)
#                 except Exception:
#                     pass

#         action, resource_type = _classify(method, path)
#         headers      = dict(scope.get("headers", []))
#         query_string = scope.get("query_string", b"").decode("utf-8", errors="replace")

#         entry = AuditEntry(
#             user_id          = user_id,
#             user_role        = user_role,
#             user_phone       = user_phone,
#             method           = method,
#             path             = path,
#             query_params     = _parse_query(query_string),
#             request_body     = _parse_body(body_bytes),
#             status_code      = status_code,
#             response_time_ms = elapsed,
#             action           = action,
#             resource_type    = resource_type,
#             resource_id      = _extract_id(path),
#             ip_address       = _get_ip(scope, headers),
#             user_agent       = headers.get(b"user-agent", b"").decode("utf-8", errors="replace") or None,
#             ts_ns            = ts_ns,
#         )

#         try:
#             _queue.put_nowait(entry)
#         except asyncio.QueueFull:
#             logger.warning("Audit queue full — dropping %s %s", method, path)


# # ── Helpers ────────────────────────────────────────────────────

# async def _read_body(receive: Receive) -> bytes:
#     chunks, more = [], True
#     while more:
#         msg = await receive()
#         chunks.append(msg.get("body", b""))
#         more = msg.get("more_body", False)
#     return b"".join(chunks)


# def _replay_receive(body: bytes):
#     sent = False

#     async def receive() -> dict:
#         nonlocal sent
#         if not sent:
#             sent = True
#             return {"type": "http.request", "body": body, "more_body": False}
#         await asyncio.Future()

#     return receive


# def _parse_body(raw: bytes) -> Optional[dict]:
#     if not raw:
#         return None
#     try:
#         data = json.loads(raw)
#         if isinstance(data, dict):
#             return {
#                 k: "***" if k.lower() in SENSITIVE_FIELDS else v
#                 for k, v in data.items()
#             }
#     except Exception:
#         pass
#     return None


# def _parse_query(qs: str) -> Optional[dict]:
#     if not qs:
#         return None
#     result = {}
#     for pair in qs.split("&"):
#         if "=" in pair:
#             k, v = pair.split("=", 1)
#             result[k] = v
#         elif pair:
#             result[pair] = ""
#     return result or None


# def _classify(method: str, path: str) -> tuple[str, str]:
#     for pattern, resource, rtype in PATH_RULES:
#         if pattern.match(path):
#             return f"{METHOD_MAP.get(method, method)}_{resource}", rtype
#     return METHOD_MAP.get(method, "UNKNOWN"), "unknown"


# def _extract_id(path: str) -> Optional[str]:
#     m = _UUID_RE.search(path)
#     return m.group(1) if m else None


# def _get_ip(scope: Scope, headers: dict) -> Optional[str]:
#     forwarded = headers.get(b"x-forwarded-for", b"").decode()
#     if forwarded:
#         return forwarded.split(",")[0].strip()
#     client = scope.get("client")
#     return client[0] if client else None







































































# app/core/middleware/audit.py
import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.loki import push_logs_to_loki

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────
QUEUE_MAX_SIZE = 10_000
BATCH_SIZE     = 100
BATCH_TIMEOUT  = 2.0
WORKER_COUNT   = 2

SKIP_PATHS = frozenset({
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
})

SKIP_PREFIXES = (
    "/api/v1/tracking/location-history/tiles",
)

SENSITIVE_FIELDS = frozenset({
    "password", "hashed_password", "token", "refresh_token",
})

PATH_RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"^/api/v1/auth/login"),   "LOGIN",         "auth"),
    (re.compile(r"^/api/v1/auth/logout"),  "LOGOUT",        "auth"),
    (re.compile(r"^/api/v1/auth/refresh"), "REFRESH_TOKEN", "auth"),
    (re.compile(r"^/api/v1/users"),        "USER",          "user"),
    (re.compile(r"^/api/v1/provinces"),    "PROVINCE",      "province"),
    (re.compile(r"^/api/v1/services"),     "SERVICE",       "service"),
    (re.compile(r"^/api/v1/map"),          "MAP",           "map"),
    (re.compile(r"^/api/v1/audit"),        "AUDIT",         "audit"),
    (re.compile(r"^/api/v1/tracking"),     "TRACKING",      "tracking"),
]

METHOD_MAP = {
    "GET":    "READ",
    "POST":   "CREATE",
    "PUT":    "UPDATE",
    "PATCH":  "PARTIAL_UPDATE",
    "DELETE": "DELETE",
}

_UUID_RE = re.compile(
    r"/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)


# ── Audit entry ────────────────────────────────────────────────

@dataclass(slots=True)
class AuditEntry:
    user_id:          Optional[str]
    user_role:        Optional[str]
    user_phone:       Optional[str]
    method:           str
    path:             str
    query_params:     Optional[dict]
    request_body:     Optional[dict]
    status_code:      int
    response_time_ms: int
    action:           str
    resource_type:    str
    resource_id:      Optional[str]
    ip_address:       Optional[str]
    user_agent:       Optional[str]
    ts_ns:            str


# ── Queue + workers ────────────────────────────────────────────

_queue: asyncio.Queue[AuditEntry] = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
_workers: list[asyncio.Task] = []


async def _batch_writer() -> None:
    while True:
        batch: list[AuditEntry] = []

        try:
            entry = await asyncio.wait_for(_queue.get(), timeout=BATCH_TIMEOUT)
            batch.append(entry)
        except asyncio.TimeoutError:
            continue

        while len(batch) < BATCH_SIZE:
            try:
                batch.append(_queue.get_nowait())
            except asyncio.QueueEmpty:
                break

        if not batch:
            continue

        loki_entries: list[tuple[str, str]] = []
        for e in batch:
            log_line = json.dumps(
                {
                    "user_id":          e.user_id,
                    "user_role":        e.user_role,
                    "user_phone":       e.user_phone,
                    "method":           e.method,
                    "path":             e.path,
                    "query_params":     e.query_params,
                    "request_body":     e.request_body,
                    "status_code":      e.status_code,
                    "response_time_ms": e.response_time_ms,
                    "action":           e.action,
                    "resource_type":    e.resource_type,
                    "resource_id":      e.resource_id,
                    "ip_address":       e.ip_address,
                    "user_agent":       e.user_agent,
                },
                ensure_ascii=False,
                default=str,
            )
            loki_entries.append((e.ts_ns, log_line))

        await push_logs_to_loki(loki_entries)
        logger.debug("Audit: pushed %d entries to Loki", len(loki_entries))

        for _ in batch:
            _queue.task_done()


def start_audit_workers() -> None:
    global _workers
    _workers = [
        asyncio.create_task(_batch_writer(), name=f"audit-loki-writer-{i}")
        for i in range(WORKER_COUNT)
    ]
    logger.info("Audit: %d Loki writer workers started", WORKER_COUNT)


async def stop_audit_workers() -> None:
    try:
        await asyncio.wait_for(_queue.join(), timeout=10.0)
    except asyncio.TimeoutError:
        logger.warning("Audit: queue not fully flushed on shutdown")
    for task in _workers:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("Audit: Loki workers stopped")


# ── Helpers ────────────────────────────────────────────────────



def _read_user_from_state(scope: Scope) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    scope["state"] is a plain dict in this Starlette/FastAPI version.
    e.g. {'current_user': <User object>}
    """
    raw_state = scope.get("state")
    if not raw_state:
        return None, None, None

    # scope["state"] is a dict — use .get() not getattr()
    user = raw_state.get("current_user") if isinstance(raw_state, dict) else getattr(raw_state, "current_user", None)

    if user is None:
        return None, None, None

    try:
        user_id    = str(user.id)
        user_role  = user.role.value if hasattr(user.role, "value") else str(user.role)
        user_phone = str(user.phone)
        return user_id, user_role, user_phone
    except Exception as exc:
        logger.warning("Audit: could not read user from state: %s", exc)
        return None, None, None



async def _read_body(receive: Receive) -> bytes:
    chunks, more = [], True
    while more:
        msg = await receive()
        chunks.append(msg.get("body", b""))
        more = msg.get("more_body", False)
    return b"".join(chunks)


def _replay_receive(body: bytes):
    sent = False

    async def receive() -> dict:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        await asyncio.Future()

    return receive


def _parse_body(raw: bytes) -> Optional[dict]:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {
                k: "***" if k.lower() in SENSITIVE_FIELDS else v
                for k, v in data.items()
            }
    except Exception:
        pass
    return None


def _parse_query(qs: str) -> Optional[dict]:
    if not qs:
        return None
    result = {}
    for pair in qs.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            result[k] = v
        elif pair:
            result[pair] = ""
    return result or None


def _classify(method: str, path: str) -> tuple[str, str]:
    for pattern, resource, rtype in PATH_RULES:
        if pattern.match(path):
            return f"{METHOD_MAP.get(method, method)}_{resource}", rtype
    return METHOD_MAP.get(method, "UNKNOWN"), "unknown"


def _extract_id(path: str) -> Optional[str]:
    m = _UUID_RE.search(path)
    return m.group(1) if m else None


def _get_ip(scope: Scope, headers: dict) -> Optional[str]:
    forwarded = headers.get(b"x-forwarded-for", b"").decode()
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else None


# ── Pure ASGI middleware ────────────────────────────────────────

class AuditMiddleware:

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path   = scope.get("path", "")
        method = scope.get("method", "GET")

        if path in SKIP_PATHS or path.startswith(SKIP_PREFIXES):
            await self.app(scope, receive, send)
            return

        start      = time.monotonic()
        body_bytes = b""

        if method in ("POST", "PUT", "PATCH"):
            body_bytes = await _read_body(receive)
            receive    = _replay_receive(body_bytes)

        status_code = 500

        async def send_wrapper(message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        # ── Run the actual route ───────────────────────────────
        await self.app(scope, receive, send_wrapper)

        # ── Everything below runs AFTER the route completes ────
        elapsed = int((time.monotonic() - start) * 1000)
        ts_ns   = str(time.time_ns())

        # Read user — safe because expire_on_commit=False keeps
        # attribute values in memory after session.close()
        user_id, user_role, user_phone = _read_user_from_state(scope)

        action, resource_type = _classify(method, path)
        headers      = dict(scope.get("headers", []))
        query_string = scope.get("query_string", b"").decode("utf-8", errors="replace")

        entry = AuditEntry(
            user_id          = user_id,
            user_role        = user_role,
            user_phone       = user_phone,
            method           = method,
            path             = path,
            query_params     = _parse_query(query_string),
            request_body     = _parse_body(body_bytes),
            status_code      = status_code,
            response_time_ms = elapsed,
            action           = action,
            resource_type    = resource_type,
            resource_id      = _extract_id(path),
            ip_address       = _get_ip(scope, headers),
            user_agent       = headers.get(
                b"user-agent", b""
            ).decode("utf-8", errors="replace") or None,
            ts_ns            = ts_ns,
        )

        try:
            _queue.put_nowait(entry)
        except asyncio.QueueFull:
            logger.warning("Audit queue full — dropping %s %s", method, path)