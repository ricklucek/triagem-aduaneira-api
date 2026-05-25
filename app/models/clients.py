from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from .base import TimestampMixin, uuid_pk


class Client(TimestampMixin, db.Model):
    __tablename__ = "clients"

    id = uuid_pk()
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey("organizations.id"), nullable=False, index=True)

    tax_id = db.Column(db.String(14), nullable=False, index=True)
    legal_name = db.Column(db.String(255), nullable=False, index=True)
    trade_name = db.Column(db.String(255), nullable=True)
    state_registration = db.Column(db.String(64), nullable=True)
    municipal_registration = db.Column(db.String(64), nullable=True)
    office_address = db.Column(db.Text, nullable=True)
    warehouse_address = db.Column(db.Text, nullable=True)
    main_cnae = db.Column(db.Text, nullable=True)
    secondary_cnae = db.Column(db.Text, nullable=True)
    tax_regime = db.Column(db.String(64), nullable=True)
    radar_mode = db.Column(db.String(64), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)

    organization = db.relationship("Organization", back_populates="clients")
    contacts = db.relationship("ClientContact", back_populates="client", lazy=True, cascade="all, delete-orphan", order_by="desc(ClientContact.primary), ClientContact.name.asc()")
    scopes = db.relationship("Scope", back_populates="client", lazy=True)

    __table_args__ = (UniqueConstraint("organization_id", "tax_id", name="uq_clients_org_tax_id"),)


class ClientContact(TimestampMixin, db.Model):
    __tablename__ = "client_contacts"

    id = uuid_pk()
    client_id = db.Column(UUID(as_uuid=True), db.ForeignKey("clients.id"), nullable=False, index=True)

    name = db.Column(db.String(255), nullable=False)
    department_role = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), nullable=True, index=True)
    phone = db.Column(db.String(64), nullable=True)
    whatsapp = db.Column(db.String(64), nullable=True)
    primary = db.Column(db.Boolean, nullable=False, default=False)
    active = db.Column(db.Boolean, nullable=False, default=True)

    client = db.relationship("Client", back_populates="contacts")
