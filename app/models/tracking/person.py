# app/models/tracking/person.py
from typing import TYPE_CHECKING, Optional
from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger, CheckConstraint, ForeignKey,
    Index, SmallInteger, String, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.tracking.city import City
    from app.models.tracking.location_history import LocationHistory


class Person(Base):
    __tablename__ = "people"
    __table_args__ = (
        CheckConstraint("gender IN ('M','F')", name="ck_people_gender"),
        CheckConstraint("age >= 0 AND age <= 120", name="ck_people_age"),
        Index("idx_people_city_id", "city_id"),
        Index("idx_people_home_location_gist", "home_location", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True,
        server_default=text("nextval('people_id_seq')"),
    )
    gender: Mapped[str] = mapped_column(String(1), nullable=False)
    age: Mapped[int]    = mapped_column(SmallInteger, nullable=False)
    city_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("cities.id"), nullable=False
    )
    home_location: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326), nullable=False
    )

    city: Mapped["City"] = relationship("City", back_populates="people", lazy="joined")
    location_history: Mapped[list["LocationHistory"]] = relationship(
        "LocationHistory", back_populates="person", lazy="dynamic"
    )