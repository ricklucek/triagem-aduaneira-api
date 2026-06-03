
from sqlalchemy import JSON, UUID, Column, ForeignKey, String, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.utils import TimestampMixin, uuid_pk

from ..extensions import Base

class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id = uuid_pk()
    nome = Column(String(255), nullable=False, unique=True, index=True)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    cnpj = Column(String(14), nullable=True, unique=True, index=True)
    email = Column(String(255), nullable=True)
    telefone = Column(String(64), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)

    users = relationship("User", back_populates="organization", lazy=True)
    clients = relationship("Client", back_populates="organization", lazy=True)
    scopes = relationship("Scope", back_populates="organization", lazy=True)
    prepostos = relationship("Preposto", back_populates="organization", lazy=True)

    settings = relationship(
        "OrganizationSetting",
        back_populates="organization",
        lazy=True,
        cascade="all, delete-orphan",
    )


class OrganizationSetting(TimestampMixin, Base):
    __tablename__ = "organization_settings"

    id = uuid_pk()
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    key = Column(String(100), nullable=False, index=True)
    value_json = Column(JSON, nullable=False, default=dict)
    updated_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    organization = relationship("Organization", back_populates="settings")
    updated_by_user = relationship("User", foreign_keys=[updated_by_user_id])

    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_org_settings_org_key"),
    )
