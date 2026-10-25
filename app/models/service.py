# app/models/service.py
import enum
import uuid
from typing import List, Optional

from sqlalchemy import Boolean, Enum as SAEnum, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.user import tenant_admin_service


class ServiceType(str, enum.Enum):
    SERVICE1 = "service1"
    SERVICE2 = "service2"
    SERVICE3 = "service3"
    SERVICE4 = "service4"


class Service(Base, TimestampMixin):
    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("service_type", name="uq_services_type"),
        Index("ix_services_type", "service_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    service_type: Mapped[ServiceType] = mapped_column(
        SAEnum(ServiceType, name="servicetype"), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tenant_admins: Mapped[List["User"]] = relationship(  # noqa: F821
        "User",
        secondary=tenant_admin_service,
        back_populates="services",
        lazy="selectin",
    )