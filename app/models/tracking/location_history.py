# app/models/tracking/location_history.py
from datetime import datetime
from typing import TYPE_CHECKING
from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.tracking.person import Person


class LocationHistory(Base):
    __tablename__ = "location_history"
    __table_args__ = (
        Index("idx_location_history_person_id",    "person_id"),
        Index("idx_location_history_timestamp",    "timestamp"),
        Index("idx_location_history_location_gist","location", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True,
        server_default=text("nextval('location_history_id_seq')"),
    )
    person_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("people.id"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    location: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326), nullable=False
    )

    person: Mapped["Person"] = relationship(
        "Person", back_populates="location_history", lazy="joined"
    )