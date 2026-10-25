# app/core/tracing.py

from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

from app.core.config import settings
from app.core.database import engine

logger = logging.getLogger(__name__)

_initialized = False


def setup_tracing(app) -> None:
    global _initialized
    if _initialized:
        return

    # ── Resource: who we are ──────────────────────────────────────
    resource = Resource.create({
        "service.name":        "map-api",
        "service.version":     "1.0.0",
        "service.namespace":   "map",
        "deployment.environment": (
            "production" if settings.is_production else "development"
        ),
    })

    # ── Sampler: 100% dev, configurable prod ──────────────────────
    sample_rate = 1.0 if not settings.is_production else 0.2
    sampler = ParentBasedTraceIdRatio(sample_rate)

    provider = TracerProvider(resource=resource, sampler=sampler)

    # ── OTLP exporter → Tempo ─────────────────────────────────────
    otlp_exporter = OTLPSpanExporter(
        endpoint="http://tempo:4317",
        insecure=True,
    )

    provider.add_span_processor(
        BatchSpanProcessor(
            otlp_exporter,
            max_queue_size=2048,
            max_export_batch_size=512,
            schedule_delay_millis=5000,
            export_timeout_millis=30000,
        )
    )

    # ── Console exporter in dev (optional) ───────────────────────
    if not settings.is_production:
        provider.add_span_processor(
            BatchSpanProcessor(ConsoleSpanExporter())
        )

    trace.set_tracer_provider(provider)

    # ── Instrument everything ─────────────────────────────────────
    FastAPIInstrumentor.instrument_app(
        app,
        server_request_hook=_server_request_hook,
        client_request_hook=_client_request_hook,
        client_response_hook=_client_response_hook,
        http_capture_headers_server_request=["x-request-id", "user-agent"],
        http_capture_headers_server_response=["x-request-id"],
    )

    SQLAlchemyInstrumentor().instrument(
        engine=engine.sync_engine,
        enable_commenter=True,        # adds SQL comments with trace info
        commenter_options={
            "db_framework": True,
        },
    )

    RedisInstrumentor().instrument()

    # If you use httpx for external calls
    HTTPXClientInstrumentor().instrument()

    _initialized = True
    logger.info(
        "OpenTelemetry tracing initialized",
        extra={"sample_rate": sample_rate, "endpoint": "http://tempo:4317"},
    )


# ── Hooks: enrich spans with extra attributes ─────────────────

def _server_request_hook(span, scope):
    """Add custom attributes to every incoming request span."""
    if span and span.is_recording():
        # You can pull from scope["headers"] etc.
        pass


def _client_request_hook(span, scope):
    pass


def _client_response_hook(span, scope, message=None):
    """Tag 4xx/5xx spans as errors automatically.

    opentelemetry-instrumentation-asgi >= 0.50b0 calls this hook with
    ``(span, scope, message)``; older releases used ``(span, message)``.
    Support both so a dependency bump cannot break tracing again.
    """
    if message is None:
        # Legacy 2-argument call: (span, message)
        message = scope

    if not span or not span.is_recording():
        return
    if not isinstance(message, dict):
        return

    status = message.get("status")
    if isinstance(status, int) and status >= 400:
        span.set_attribute("error", True)
        span.set_attribute("http.response.status_code", status)