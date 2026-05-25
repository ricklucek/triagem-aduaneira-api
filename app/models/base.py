from datetime import datetime
import uuid

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=True,
    )


def uuid_pk():
    return db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
