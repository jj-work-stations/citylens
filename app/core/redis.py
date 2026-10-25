# app/core/redis.py
import os
import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=False,
    encoding="utf-8",
    max_connections=20,
    socket_timeout=5,           # ← fail fast if Redis hangs
    socket_connect_timeout=5,   # ← fail fast on connect
    socket_keepalive=True,      # ← detect dead connections
    health_check_interval=30,   # ← auto-ping every 30s
)