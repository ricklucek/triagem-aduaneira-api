from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Index, String

from app.extensions import Base


class FiscalMunicipality(Base):
    """Município brasileiro de referência para preenchimento fiscal."""

    __tablename__ = "fiscal_municipalities"

    code = Column(String(7), primary_key=True)
    name = Column(String(120), nullable=False, index=True)
    state = Column(String(2), nullable=False, index=True)
    active = Column(Boolean, nullable=False, default=True, index=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        Index("ix_fiscal_municipalities_state_name", "state", "name"),
    )


class FiscalCountry(Base):
    """País fiscal identificado pelos códigos BACEN e ISO.

    A vigência é avaliada contra a data de emissão da NF-e. Datas nulas
    representam limites abertos.
    """

    __tablename__ = "fiscal_countries"

    bacen_code = Column(String(4), primary_key=True)
    iso_alpha_2 = Column(String(2), nullable=True, index=True)
    iso_alpha_3 = Column(String(3), nullable=True, index=True)
    name = Column(String(120), nullable=False, index=True)
    valid_from = Column(Date, nullable=True, index=True)
    valid_until = Column(Date, nullable=True, index=True)
    active = Column(Boolean, nullable=False, default=True, index=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        Index("ix_fiscal_countries_active_validity", "active", "valid_from", "valid_until"),
    )
