from datetime import datetime

from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from ..auth import admin_required, auth_required
from ..extensions import db
from ..schemas.nfe_carrier import (
    CreateNfeCarrierSchema,
    NfeCarrierListQuerySchema,
    NfeCarrierSchema,
    UpdateNfeCarrierSchema,
)
from ..services.nfe_carrier import (
    NfeCarrierAlreadyExistsError,
    NfeCarrierService,
)
from .route_helpers import json_payload, uuid_or_404, validation_error_response


nfe_carrier_bp = Blueprint("nfe_carriers", __name__, url_prefix="/nfe-carriers")
carrier_schema = NfeCarrierSchema()
carrier_list_schema = NfeCarrierSchema(many=True)
list_query_schema = NfeCarrierListQuerySchema()
create_schema = CreateNfeCarrierSchema()
update_schema = UpdateNfeCarrierSchema()


def _service() -> NfeCarrierService:
    return NfeCarrierService(g.current_user)


@nfe_carrier_bp.get("")
@auth_required
def list_nfe_carriers():
    try:
        params = list_query_schema.load(request.args)
        rows, total = _service().list(
            query=params["q"],
            active=params["active"],
            limit=params["limit"],
            offset=params["offset"],
        )
    except ValidationError as exc:
        return validation_error_response(exc)
    except ValueError as exc:
        return jsonify({"error": "organization_required", "message": str(exc)}), 400

    return jsonify(
        {
            "items": carrier_list_schema.dump(rows),
            "total": total,
            "limit": params["limit"],
            "offset": params["offset"],
            "q": params["q"],
            "active": params["active"],
        }
    )


@nfe_carrier_bp.post("")
@admin_required
def create_nfe_carrier():
    try:
        data = create_schema.load(json_payload())
        carrier = _service().create(data)
        db.session.commit()
        return jsonify(carrier_schema.dump(carrier)), 201
    except ValidationError as exc:
        db.session.rollback()
        return validation_error_response(exc)
    except NfeCarrierAlreadyExistsError as exc:
        db.session.rollback()
        return jsonify(
            {
                "error": "carrier_already_exists",
                "message": str(exc),
                "carrier_id": str(exc.existing_id),
            }
        ), 409
    except ValueError as exc:
        db.session.rollback()
        return jsonify(
            {
                "error": "bad_request",
                "message": str(exc),
            }
        ), 400


@nfe_carrier_bp.get("/<carrier_id>")
@auth_required
def get_nfe_carrier(carrier_id: str):
    carrier = _service().get(uuid_or_404(carrier_id))
    if not carrier:
        return jsonify({"error": "not_found", "message": "Transportadora não encontrada."}), 404
    return jsonify(carrier_schema.dump(carrier))


@nfe_carrier_bp.patch("/<carrier_id>")
@admin_required
def update_nfe_carrier(carrier_id: str):
    service = _service()
    carrier = service.get(uuid_or_404(carrier_id))
    if not carrier:
        return jsonify({"error": "not_found", "message": "Transportadora não encontrada."}), 404
    try:
        data = update_schema.load(json_payload())
        if not data:
            raise ValidationError({"_schema": ["Informe ao menos um campo para atualizar."]})
        carrier = service.update(carrier, data)
        db.session.commit()
        return jsonify(carrier_schema.dump(carrier))
    except ValidationError as exc:
        db.session.rollback()
        return validation_error_response(exc)
    except NfeCarrierAlreadyExistsError as exc:
        db.session.rollback()
        return jsonify(
            {
                "error": "carrier_already_exists",
                "message": str(exc),
                "carrier_id": str(exc.existing_id),
            }
        ), 409
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": "bad_request", "message": str(exc)}), 400


@nfe_carrier_bp.delete("/<carrier_id>")
@admin_required
def deactivate_nfe_carrier(carrier_id: str):
    service = _service()
    carrier = service.get(uuid_or_404(carrier_id))
    if not carrier:
        return jsonify({"error": "not_found", "message": "Transportadora não encontrada."}), 404
    carrier.active = False
    carrier.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(carrier_schema.dump(carrier))
