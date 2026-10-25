# app/models/user.py
import enum
import uuid
from typing import List, Optional

from sqlalchemy import (
    Boolean, Column, Enum as SAEnum,
    ForeignKey, Index, SmallInteger, String, Table, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class UserRole(str, enum.Enum):
    ADMIN        = "admin"
    TENANT_ADMIN = "tenant_admin"


class UserStatus(str, enum.Enum):
    ACTIVE    = "active"
    INACTIVE  = "inactive"
    SUSPENDED = "suspended"


# ── M2M tables ─────────────────────────────────────────────────
tenant_admin_province = Table(
    "tenant_admin_province",
    Base.metadata,
    Column("user_id",     UUID(as_uuid=True), ForeignKey("users.id",     ondelete="CASCADE"), primary_key=True),
    Column("province_id", UUID(as_uuid=True), ForeignKey("provinces.id", ondelete="CASCADE"), primary_key=True),
)

tenant_admin_service = Table(
    "tenant_admin_service",
    Base.metadata,
    Column("user_id",    UUID(as_uuid=True), ForeignKey("users.id",    ondelete="CASCADE"), primary_key=True),
    Column("service_id", UUID(as_uuid=True), ForeignKey("services.id", ondelete="CASCADE"), primary_key=True),
)

tenant_admin_city = Table(
    "tenant_admin_city",
    Base.metadata,
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "city_id",
        SmallInteger,
        ForeignKey("cities.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("phone",         name="uq_users_phone"),
        UniqueConstraint("national_code", name="uq_users_national_code"),
        Index("ix_users_phone",  "phone"),
        Index("ix_users_role",   "role"),
        Index("ix_users_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    phone:           Mapped[str]           = mapped_column(String(15),  nullable=False)
    first_name:      Mapped[str]           = mapped_column(String(100), nullable=False)
    last_name:       Mapped[str]           = mapped_column(String(100), nullable=False)
    national_code:   Mapped[Optional[str]] = mapped_column(String(10),  nullable=True)
    hashed_password: Mapped[str]           = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="userrole"),
        nullable=False,
        default=UserRole.TENANT_ADMIN,
    )
    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus, name="userstatus"),
        nullable=False,
        default=UserStatus.ACTIVE,
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Relationships ───────────────────────────────────────────
    provinces: Mapped[List["Province"]] = relationship(  # noqa: F821
        "Province",
        secondary=tenant_admin_province,
        back_populates="tenant_admins",
        lazy="selectin",
    )
    services: Mapped[List["Service"]] = relationship(  # noqa: F821
        "Service",
        secondary=tenant_admin_service,
        back_populates="tenant_admins",
        lazy="selectin",
    )
    # NEW
    cities: Mapped[List["City"]] = relationship(  # noqa: F821
        "City",
        secondary=tenant_admin_city,
        back_populates="tenant_admins",
        lazy="selectin",
    )

    # ── Helpers ────────────────────────────────────────────────
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_tenant_admin(self) -> bool:
        return self.role == UserRole.TENANT_ADMIN

    def has_province_access(self, province_id: uuid.UUID) -> bool:
        if self.is_admin:
            return True
        return any(p.id == province_id for p in self.provinces)

    def has_service_access(self, service_id: uuid.UUID) -> bool:
        if self.is_admin:
            return True
        return any(s.id == service_id for s in self.services)

    def has_city_access(self, city_id: int) -> bool:
        """Admin sees all; tenant_admin only sees assigned cities."""
        if self.is_admin:
            return True
        return any(c.id == city_id for c in self.cities)

    @property
    def allowed_city_ids(self) -> Optional[List[int]]:
        """
        Returns None for admin (unrestricted).
        Returns list of city IDs for tenant_admin.
        """
        if self.is_admin:
            return None
        return [c.id for c in self.cities]