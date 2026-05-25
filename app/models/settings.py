from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from .base import TimestampMixin, uuid_pk


class OrganizationSetting(TimestampMixin, db.Model):
    __tablename__ = "organization_settings"

    id = uuid_pk()
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey("organizations.id"), nullable=False, index=True)
    key = db.Column(db.String(100), nullable=False, index=True)
    value_json = db.Column(db.JSON, nullable=False, default=dict)
    updated_by_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=True, index=True)

    organization = db.relationship("Organization", back_populates="settings")
    updated_by_user = db.relationship("User", foreign_keys=[updated_by_user_id])

    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_org_settings_org_key"),)
