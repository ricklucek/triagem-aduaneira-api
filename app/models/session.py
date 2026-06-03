from datetime import datetime

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy import Column, DateTime, ForeignKey, String, Boolean
from sqlalchemy.orm import relationship

from app.models.utils import uuid_pk

from ..extensions import Base

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = uuid_pk()
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    token = Column(String(1024), nullable=False, unique=True, index=True)
    revoked = Column(Boolean, nullable=False, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")
