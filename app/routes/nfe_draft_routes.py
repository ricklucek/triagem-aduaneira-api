from flask import Blueprint, g, jsonify
from marshmallow import ValidationError

from ..auth import auth_required
from ..extensions import db
from ..models.import_process import NfeDraftItem, NfeXmlVersion
from ..schemas.import_process import (
    GenerateXmlSchema,
    NfeDraftItemSchema,
    NfeDraftSchema,
    NfeXmlVersionSchema,
    UpdateNfeDraftItemSchema,
)
from ..services.import_process import ImportNfeService
from .route_helpers import (
    bad_request_response,
    json_payload,
    uuid_or_404,
    validation_error_response,
)


nfe_draft_bp = Blueprint("nfe_drafts", __name__, url_prefix="/nfe-drafts")

nfe_draft_schema = NfeDraftSchema()
nfe_draft_item_schema = NfeDraftItemSchema()
nfe_xml_version_schema = NfeXmlVersionSchema()


def _service() -> ImportNfeService:
    return ImportNfeService(current_user=g.current_user)


@nfe_draft_bp.get("/<draft_id>")
@auth_required
def get_nfe_draft(draft_id: str):
    draft_uuid = uuid_or_404(draft_id)
    service = _service()
    draft = (
        service.nfe_draft_query_for_current_user()
        .filter_by(id=draft_uuid)
        .first_or_404()
    )
    detail = service.get_nfe_draft_detail(draft)
    return jsonify(
        {
            "draft": nfe_draft_schema.dump(detail["draft"]),
            "items": nfe_draft_item_schema.dump(detail["items"], many=True),
            "xmlVersions": nfe_xml_version_schema.dump(
                detail["xml_versions"], many=True
            ),
        }
    )


@nfe_draft_bp.post("/<draft_id>/validate")
@auth_required
def validate_nfe_draft(draft_id: str):
    draft_uuid = uuid_or_404(draft_id)
    service = _service()
    draft = (
        service.nfe_draft_query_for_current_user()
        .filter_by(id=draft_uuid)
        .first_or_404()
    )

    try:
        validation = service.validate_draft(draft)
        db.session.commit()
        return jsonify(validation.to_dict())
    except ValueError as exc:
        db.session.rollback()
        return bad_request_response(exc)


@nfe_draft_bp.patch("/<draft_id>/items/<item_id>")
@auth_required
def update_nfe_draft_item(draft_id: str, item_id: str):
    draft_uuid = uuid_or_404(draft_id)
    item_uuid = uuid_or_404(item_id)
    service = _service()
    draft = (
        service.nfe_draft_query_for_current_user()
        .filter_by(id=draft_uuid)
        .first_or_404()
    )
    item = NfeDraftItem.query.filter_by(
        id=item_uuid, nfe_draft_id=draft.id
    ).first_or_404()

    try:
        payload = UpdateNfeDraftItemSchema().load(json_payload())
        item = service.update_draft_item(draft, item, payload)
        db.session.commit()
        return jsonify(nfe_draft_item_schema.dump(item))
    except ValidationError as exc:
        db.session.rollback()
        return validation_error_response(exc)
    except ValueError as exc:
        db.session.rollback()
        return bad_request_response(exc)


@nfe_draft_bp.post("/<draft_id>/generate-access-key")
@auth_required
def generate_nfe_draft_access_key(draft_id: str):
    draft_uuid = uuid_or_404(draft_id)

    try:
        result = _service().generate_access_key_for_draft(draft_uuid)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return bad_request_response(exc)

    return jsonify(
        {
            "draft_id": str(result["draft"].id),
            "number": result["draft"].number,
            "access_key": result["access_key"]["access_key"],
            "cUF": result["access_key"]["cUF"],
            "AAMM": result["access_key"]["AAMM"],
            "CNPJ": result["access_key"]["CNPJ"],
            "model": result["access_key"]["model"],
            "series": result["access_key"]["series"],
            "tpEmis": result["access_key"]["tpEmis"],
            "cNF": result["access_key"]["cNF"],
            "cDV": result["access_key"]["cDV"],
            "validation": result["validation"],
        }
    )


@nfe_draft_bp.post("/<draft_id>/generate-xml")
@auth_required
def generate_nfe_unsigned_xml(draft_id: str):
    draft_uuid = uuid_or_404(draft_id)
    service = _service()
    draft = (
        service.nfe_draft_query_for_current_user()
        .filter_by(id=draft_uuid)
        .first_or_404()
    )

    try:
        GenerateXmlSchema().load(json_payload())
        row = service.generate_unsigned_xml(draft)
        db.session.commit()
        return jsonify(nfe_xml_version_schema.dump(row)), 201
    except ValidationError as exc:
        db.session.rollback()
        return validation_error_response(exc)
    except ValueError as exc:
        db.session.rollback()
        return bad_request_response(exc)


@nfe_draft_bp.get("/<draft_id>/xml-versions")
@auth_required
def list_nfe_xml_versions(draft_id: str):
    draft_uuid = uuid_or_404(draft_id)
    service = _service()
    draft = (
        service.nfe_draft_query_for_current_user()
        .filter_by(id=draft_uuid)
        .first_or_404()
    )
    rows = (
        NfeXmlVersion.query.filter(NfeXmlVersion.nfe_draft_id == draft.id)
        .order_by(NfeXmlVersion.version_number.desc())
        .all()
    )
    return jsonify(nfe_xml_version_schema.dump(rows, many=True))
