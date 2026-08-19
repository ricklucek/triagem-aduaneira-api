from flask import Blueprint, g, jsonify
from marshmallow import ValidationError

from ..auth import auth_required
from ..extensions import db
from ..models.import_process import NfeNumberSequence
from ..schemas.import_process import (
    NfeNumberSequenceSchema,
    UpsertNfeNumberSequenceSchema,
)
from ..services.nfe_number_service import NfeNumberSequenceService
from .route_helpers import (
    bad_request_response,
    json_payload,
    uuid_or_404,
    validation_error_response,
)


nfe_number_sequence_bp = Blueprint(
    "nfe_number_sequences", __name__, url_prefix="/clients"
)

nfe_number_sequence_schema = NfeNumberSequenceSchema()
nfe_number_sequence_list_schema = NfeNumberSequenceSchema(many=True)
upsert_nfe_number_sequence_schema = UpsertNfeNumberSequenceSchema()


def _service() -> NfeNumberSequenceService:
    return NfeNumberSequenceService(current_user=g.current_user)


@nfe_number_sequence_bp.get("/<client_id>/nfe-number-sequences")
@auth_required
def list_client_nfe_number_sequences(client_id: str):
    client_uuid = uuid_or_404(client_id)
    rows = (
        NfeNumberSequence.query.filter(
            NfeNumberSequence.organization_id == g.current_user.organization_id,
            NfeNumberSequence.client_id == client_uuid,
        )
        .order_by(
            NfeNumberSequence.environment.asc(),
            NfeNumberSequence.model.asc(),
            NfeNumberSequence.series.asc(),
        )
        .all()
    )
    return jsonify(nfe_number_sequence_list_schema.dump(rows))


@nfe_number_sequence_bp.put("/<client_id>/nfe-number-sequences")
@auth_required
def upsert_client_nfe_number_sequence(client_id: str):
    client_uuid = uuid_or_404(client_id)

    try:
        data = upsert_nfe_number_sequence_schema.load(json_payload())
        sequence = _service().create_or_update_nfe_number_sequence(
            client_id=client_uuid,
            environment=data["environment"],
            model=data.get("model", "55"),
            series=data["series"],
            current_number=data.get("current_number", 0),
            initial_number=data.get("initial_number", 1),
            max_number=data.get("max_number", 999999999),
            status=data.get("status", "active"),
        )
        db.session.commit()
        return jsonify(nfe_number_sequence_schema.dump(sequence))
    except ValidationError as exc:
        db.session.rollback()
        return validation_error_response(exc)
    except ValueError as exc:
        db.session.rollback()
        return bad_request_response(exc)
