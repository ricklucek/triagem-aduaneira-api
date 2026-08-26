from uuid import UUID

from flask import abort, jsonify, request
from marshmallow import ValidationError


def json_payload() -> dict:
    payload = request.get_json(silent=True) or {}
    return payload if isinstance(payload, dict) else {}


def validation_error_response(exc: ValidationError):
    environment_fields = {"environment", "provider_environment"}
    if environment_fields.intersection(exc.messages):
        return (
            jsonify(
                {
                    "error": "environment_not_allowed",
                    "message": (
                        "Novas operações de NF-e e Portal Único aceitam "
                        "somente o ambiente production."
                    ),
                    "messages": exc.messages,
                }
            ),
            400,
        )
    return jsonify({"error": "validation_error", "messages": exc.messages}), 400


def bad_request_response(exc: Exception):
    return jsonify({"error": "bad_request", "message": str(exc)}), 400


def uuid_or_404(value: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        abort(404)
