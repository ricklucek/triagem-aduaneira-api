from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from .base import TimestampMixin, uuid_pk
from .enums import OperationType, enum_column


class Preposto(TimestampMixin, db.Model):
    __tablename__ = "prepostos"

    id = uuid_pk()
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey("organizations.id"), nullable=True, index=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    legal_name = db.Column(db.String(255), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    notes = db.Column(db.Text, nullable=True)

    organization = db.relationship("Organization", back_populates="prepostos")
    contacts = db.relationship("PrepostoContact", back_populates="preposto", lazy=True, cascade="all, delete-orphan", order_by="desc(PrepostoContact.primary), PrepostoContact.name.asc()")
    locations = db.relationship("PrepostoLocation", back_populates="preposto", lazy=True, cascade="all, delete-orphan", order_by="PrepostoLocation.city.asc()")
    scope_links = db.relationship("ScopePreposto", back_populates="preposto", lazy=True, cascade="all, delete-orphan")


class PrepostoContact(TimestampMixin, db.Model):
    __tablename__ = "preposto_contacts"

    id = uuid_pk()
    preposto_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prepostos.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=True, index=True)
    phone = db.Column(db.String(64), nullable=True)
    whatsapp = db.Column(db.String(64), nullable=True)
    primary = db.Column(db.Boolean, nullable=False, default=False)

    preposto = db.relationship("Preposto", back_populates="contacts")


class PrepostoLocation(TimestampMixin, db.Model):
    __tablename__ = "preposto_locations"

    id = uuid_pk()
    preposto_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prepostos.id"), nullable=False, index=True)
    city = db.Column(db.String(255), nullable=False, index=True)
    state = db.Column(db.String(2), nullable=True, index=True)
    place_description = db.Column(db.String(255), nullable=True)
    place_type = db.Column(db.String(32), nullable=True)
    serves_import = db.Column(db.Boolean, nullable=False, default=False)
    serves_export = db.Column(db.Boolean, nullable=False, default=False)
    import_amount = db.Column(db.Numeric(12, 2), nullable=True)
    export_amount = db.Column(db.Numeric(12, 2), nullable=True)
    import_amount_description = db.Column(db.String(255), nullable=True)
    export_amount_description = db.Column(db.String(255), nullable=True)
    currency = db.Column(db.String(8), nullable=False, default="BRL")
    notes = db.Column(db.Text, nullable=True)

    preposto = db.relationship("Preposto", back_populates="locations")

    __table_args__ = (
        db.Index("ix_preposto_locations_city_state", "city", "state"),
        db.Index("ix_preposto_locations_operation", "city", "serves_import", "serves_export"),
    )


class ScopePreposto(TimestampMixin, db.Model):
    __tablename__ = "scope_prepostos"

    id = uuid_pk()
    scope_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scopes.id"), nullable=False, index=True)
    preposto_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prepostos.id"), nullable=True, index=True)
    operation_type = db.Column(enum_column(OperationType, "scope_preposto_operation_type"), nullable=False, index=True)
    enabled = db.Column(db.Boolean, nullable=False, default=False)
    amount = db.Column(db.Numeric(12, 2), nullable=True)
    included_in_casco_customs_clearance = db.Column(db.Boolean, nullable=True)
    other_port = db.Column(db.String(255), nullable=True)
    other_border = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    manual_preposto_name = db.Column(db.String(255), nullable=True)
    manual_preposto_notes = db.Column(db.Text, nullable=True)

    scope = db.relationship("Scope", back_populates="prepostos")
    preposto = db.relationship("Preposto", back_populates="scope_links")
    cities = db.relationship("ScopePrepostoCity", back_populates="scope_preposto", lazy=True, cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("scope_id", "preposto_id", "operation_type", name="uq_scope_preposto_unique"),)


class ScopePrepostoCity(TimestampMixin, db.Model):
    __tablename__ = "scope_preposto_cities"

    id = uuid_pk()
    scope_preposto_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scope_prepostos.id"), nullable=False, index=True)
    city = db.Column(db.String(255), nullable=False)
    state = db.Column(db.String(2), nullable=True)

    scope_preposto = db.relationship("ScopePreposto", back_populates="cities")

    __table_args__ = (UniqueConstraint("scope_preposto_id", "city", "state", name="uq_scope_preposto_city"),)
