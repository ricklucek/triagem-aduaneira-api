from datetime import datetime

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy import Column, DateTime, String
from werkzeug.security import check_password_hash, generate_password_hash

import uuid

class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=True,
    )


class PasswordMixin:
    password_hash = Column(String(255), nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


def uuid_pk():
    return Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)