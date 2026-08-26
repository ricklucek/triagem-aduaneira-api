from flask import Blueprint, g, jsonify
from marshmallow import ValidationError

from ..auth import admin_required, auth_required
from ..extensions import db
from ..schemas.client import ClientFiscalProfileSchema
from ..services.import_process import ImportNfeService
from .route_helpers import (
    bad_request_response,
    json_payload,
    uuid_or_404,
    validation_error_response,
)


client_fiscal_profile_bp = Blueprint(
    "client_fiscal_profiles", __name__, url_prefix="/clients"
)

client_fiscal_profile_schema = ClientFiscalProfileSchema()


def _service() -> ImportNfeService:
    return ImportNfeService(current_user=g.current_user)


@client_fiscal_profile_bp.get("/<client_id>/fiscal-profile")
@auth_required
def get_client_fiscal_profile(client_id: str):
    client_uuid = uuid_or_404(client_id)

    try:
        profile = _service().get_importer_fiscal_profile(client_uuid)
    except ValueError as exc:
        return jsonify({"error": "not_found", "message": str(exc)}), 404

    return jsonify(client_fiscal_profile_schema.dump(profile))


@client_fiscal_profile_bp.put("/<client_id>/fiscal-profile")
@admin_required
def upsert_client_fiscal_profile(client_id: str):
    client_uuid = uuid_or_404(client_id)
    payload = json_payload()
    payload["client_id"] = client_uuid

    try:
        data = client_fiscal_profile_schema.load(payload)
        profile = _service().create_or_update_client_fiscal_profile(data)
        db.session.commit()
        return jsonify(client_fiscal_profile_schema.dump(profile))
    except ValidationError as exc:
        db.session.rollback()
        return validation_error_response(exc)
    except ValueError as exc:
        db.session.rollback()
        return bad_request_response(exc)
