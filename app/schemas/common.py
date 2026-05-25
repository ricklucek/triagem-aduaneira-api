from enum import Enum
from uuid import UUID

from marshmallow import ValidationError, fields


class UUIDStringField(fields.Field):
    """Serializes UUID objects as strings and accepts UUID-like strings on load."""

    default_error_messages = {
        "invalid": "Invalid UUID.",
    }

    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return None
        return str(value)

    def _deserialize(self, value, attr, data, **kwargs):
        if value in (None, ""):
            if self.allow_none:
                return None
            raise ValidationError(self.error_messages["invalid"])

        try:
            return UUID(str(value))
        except (TypeError, ValueError):
            raise ValidationError(self.error_messages["invalid"])


class EnumField(fields.Field):
    """Serializes/deserializes enum values as strings.

    Works with Python Enum members and with raw strings already loaded
    from SQLAlchemy Enum columns.
    """

    default_error_messages = {
        "invalid": "Invalid enum value.",
    }

    def __init__(self, enum_class: type[Enum], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enum_class = enum_class
        self.allowed_values = [item.value for item in enum_class]

    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return None
        if isinstance(value, self.enum_class):
            return value.value
        return str(value)

    def _deserialize(self, value, attr, data, **kwargs):
        if value in (None, ""):
            if self.allow_none:
                return None
            raise ValidationError(self.error_messages["invalid"])

        if isinstance(value, self.enum_class):
            return value

        if value not in self.allowed_values:
            raise ValidationError(
                f"{self.error_messages['invalid']} Allowed values: {', '.join(self.allowed_values)}"
            )

        return self.enum_class(value)


class DateTimeMixinSchema:
    createdAt = fields.DateTime(attribute="created_at", allow_none=True, dump_only=True)
    updatedAt = fields.DateTime(attribute="updated_at", allow_none=True, dump_only=True)
