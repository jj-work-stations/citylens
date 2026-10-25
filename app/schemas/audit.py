# app/schemas/audit.py
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    """
    Loki returns plain JSON dicts — no ORM, no auto id.
    All fields are Optional because log entries may vary.
    """
    # No 'id' field — Loki uses nanosecond timestamps as identifiers
    # Use created_at as the unique identifier for display

    user_id:          Optional[str]  = None
    user_role:        Optional[str]  = None
    user_phone:       Optional[str]  = None
    method:           Optional[str]  = None
    path:             Optional[str]  = None
    query_params:     Optional[dict] = None
    request_body:     Optional[dict] = None
    status_code:      Optional[int]  = None
    response_time_ms: Optional[int]  = None
    action:           Optional[str]  = None
    resource_type:    Optional[str]  = None
    resource_id:      Optional[str]  = None
    ip_address:       Optional[str]  = None
    user_agent:       Optional[str]  = None
    created_at:       Optional[datetime] = None