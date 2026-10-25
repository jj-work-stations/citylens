# app/main.py
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

import app.models  # noqa: F401

from app.apis.v1.router import router as v1_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.loki import close_loki_client, get_loki_client
from app.core.middleware.audit import (
    AuditMiddleware,
    start_audit_workers,
    stop_audit_workers,
)
from app.core.tracing import setup_tracing


logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | pid=%(process)d | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pid = os.getpid()
    logger.info("Worker pid=%s starting …", pid)

    # Postgres
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Worker pid=%s — Postgres ready.", pid)

    # Loki client (lightweight — just an httpx client)
    get_loki_client()
    logger.info("Worker pid=%s — Loki client ready.", pid)

    # Audit background writers
    start_audit_workers()
    logger.info("Worker pid=%s — audit workers started.", pid)

    yield

    # Shutdown
    logger.info("Worker pid=%s shutting down …", pid)
    await stop_audit_workers()
    await close_loki_client()
    await engine.dispose()
    logger.info("Worker pid=%s — shutdown complete.", pid)


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
    docs_url  = "/docs"   if not settings.is_production else None,
    redoc_url = "/redoc"  if not settings.is_production else None,
)


setup_tracing(app)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(AuditMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        ctx = error.get("ctx", {})
        safe_ctx = {k: str(v) for k, v in ctx.items()} if ctx else {}
        errors.append({
            "field":   " → ".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type":    error["type"],
            **({"ctx": safe_ctx} if safe_ctx else {}),
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors},
    )


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app.include_router(v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "worker_pid": os.getpid()}