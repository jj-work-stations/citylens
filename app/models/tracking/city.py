# app/models/tracking/city.py
from typing import TYPE_CHECKING, List
from geoalchemy2 import Geometry
from sqlalchemy import Index, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.user import tenant_admin_city   # import the association table

if TYPE_CHECKING:
    from app.models.tracking.person import Person
    from app.models.user import User


class City(Base):
    __tablename__ = "cities"
    __table_args__ = (
        Index("idx_cities_geom_gist", "geom", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(
        SmallInteger,
        primary_key=True,
        server_default=text("nextval('cities_id_seq')"),
    )
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326), nullable=False
    )

    people: Mapped[list["Person"]] = relationship(
        "Person", back_populates="city"
    )
    tenant_admins: Mapped[List["User"]] = relationship(
        "User",
        secondary=tenant_admin_city,
        back_populates="cities",
        lazy="selectin",
    )