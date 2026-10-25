# app/models/province.py
import uuid
from typing import List, Optional

from sqlalchemy import Boolean, Float, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.user import tenant_admin_province


class Province(Base, TimestampMixin):
    __tablename__ = "provinces"
    __table_args__ = (
        UniqueConstraint("code", name="uq_provinces_code"),
        Index("ix_provinces_code", "code"),
        Index("ix_provinces_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    center_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    center_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    bbox_xmin: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_ymin: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_xmax: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_ymax: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tenant_admins: Mapped[List["User"]] = relationship(  # noqa: F821
        "User",
        secondary=tenant_admin_province,
        back_populates="provinces",
        lazy="selectin",
    )

    @property
    def bbox(self) -> Optional[str]:
        vals = [self.bbox_xmin, self.bbox_ymin, self.bbox_xmax, self.bbox_ymax]
        if all(v is not None for v in vals):
            return ",".join(str(v) for v in vals)
        return None