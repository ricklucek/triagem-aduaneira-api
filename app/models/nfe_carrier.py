from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.utils import uuid_pk

from ..extensions import Base


class NfeCarrier(Base):
    __tablename__ = "nfe_carriers"

    id = uuid_pk()
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    legal_name = Column(String(60), nullable=False, index=True)
    trade_name = Column(String(60), nullable=True, index=True)
    tax_id = Column(String(14), nullable=False, index=True)
    state_registration = Column(String(30), nullable=True)

    street = Column(String(255), nullable=False)
    number = Column(String(60), nullable=False)
    complement = Column(String(255), nullable=True)
    district = Column(String(120), nullable=False)
    municipality_code = Column(String(7), nullable=False, index=True)
    municipality_name = Column(String(120), nullable=False)
    state = Column(String(2), nullable=False, index=True)
    zip_code = Column(String(8), nullable=False)

    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    organization = relationship("Organization")

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "tax_id",
            name="uq_nfe_carriers_org_tax_id",
        ),
    )
