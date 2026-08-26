from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from ..auth import admin_required, auth_required
from ..extensions import db
from ..schemas.import_process import (
    CreateProviderConnectionSchema,
    ExternalProviderConnectionSchema,
    ProviderConnectionListQuerySchema,
)
from ..services.import_process import ImportNfeService
from .route_helpers import (
    bad_request_response,
    json_payload,
    uuid_or_404,
    validation_error_response,
)


provider_connection_bp = Blueprint(
    "external_provider_connections",
    __name__,
    url_prefix="/external-provider-connections",
)

provider_connection_schema = ExternalProviderConnectionSchema()


def _service() -> ImportNfeService:
    return ImportNfeService(current_user=g.current_user)


@provider_connection_bp.post("")
@admin_required
def create_provider_connection():
    try:
        payload = CreateProviderConnectionSchema().load(json_payload())
        connection = _service().create_provider_connection(payload)
        db.session.commit()
        return jsonify(provider_connection_schema.dump(connection)), 201
    except ValidationError as exc:
        db.session.rollback()
        return validation_error_response(exc)
    except ValueError as exc:
        db.session.rollback()
        return bad_request_response(exc)


@provider_connection_bp.get("")
@auth_required
def list_provider_connections():
    try:
        params = ProviderConnectionListQuerySchema().load(request.args)
        result = _service().list_provider_connections(params)
        return jsonify(
            {
                "items": provider_connection_schema.dump(result["items"], many=True),
                "total": result["total"],
                "limit": result["limit"],
                "offset": result["offset"],
            }
        )
    except ValidationError as exc:
        return validation_error_response(exc)


@provider_connection_bp.get("/<connection_id>")
@auth_required
def get_provider_connection(connection_id: str):
    connection_uuid = uuid_or_404(connection_id)
    service = _service()
    connection = (
        service.provider_connection_query_for_current_user()
        .filter_by(id=connection_uuid)
        .first_or_404()
    )
    return jsonify(provider_connection_schema.dump(connection))
