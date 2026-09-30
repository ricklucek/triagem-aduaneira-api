from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.utils import uuid_pk

from ..extensions import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = uuid_pk()
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    actor_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_name = Column(String(255), nullable=False)
    actor_email = Column(String(255), nullable=True)
    module = Column(String(32), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(32), nullable=False, index=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    operation_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    details = Column("metadata", JSON, nullable=False, default=dict)
    reverses_event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("ix_audit_events_org_created", "organization_id", "created_at"),
        Index("ix_audit_events_org_operation", "organization_id", "operation_id"),
    )


class AuditEventChange(Base):
    __tablename__ = "audit_event_changes"

    id = uuid_pk()
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    entity_type = Column(String(32), nullable=False, index=True)
    entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    scope_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scopes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    subject_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    changed_fields = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_audit_event_changes_event_entity", "event_id", "entity_id"),
    )
