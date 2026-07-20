from uuid import UUID

from flask import Blueprint, abort, g, jsonify, request
from marshmallow import ValidationError

from app.schemas.client import ClientFiscalProfileSchema
from app.services.nfe_number_service import NfeNumberSequenceService

from ..auth import auth_required
from ..extensions import db
from ..models.import_process import DuimpSnapshot, NfeDraftItem, NfeXmlVersion
from ..schemas.import_process import (
    CreateImportProcessSchema,
    CreateManualDuimpSnapshotSchema,
    CreateNfeDraftFromDuimpSchema,
    CreateProviderConnectionSchema,
    DuimpSnapshotSchema,
    ExternalProviderConnectionSchema,
    GenerateXmlSchema,
    ImportProcessListQuerySchema,
    ImportProcessSchema,
    NfeDraftItemSchema,
    NfeDraftSchema,
    NfeNumberSequenceSchema,
    NfeXmlVersionSchema,
    ProviderConnectionListQuerySchema,
    UpdateImportProcessSchema,
    UpdateNfeDraftItemSchema,
    UpsertNfeNumberSequenceSchema,
)
from ..services.import_process import ImportNfeService
from ..models.import_process import (
    ExternalAuthType,
    ExternalConnectionStatus,
    ExternalProvider,
    FiscalEnvironment,
    HttpMethod,
    ImportProcessSource,
    ImportProcessStatus,
    ImportPurpose,
    NfeDraftStatus,
    NfeModel,
    NfeOperationType,
    NfePurpose,
    NfeXmlType,
    NfeNumberSequence
)
from app.models.import_process import NfeNumberSequence


import_process_bp = Blueprint("import_processes", __name__, url_prefix="/import-processes")
provider_connection_bp = Blueprint("external_provider_connections", __name__, url_prefix="/external-provider-connections")
nfe_draft_bp = Blueprint("nfe_drafts", __name__, url_prefix="/nfe-drafts")

import_process_schema = ImportProcessSchema()
provider_connection_schema = ExternalProviderConnectionSchema()
duimp_snapshot_schema = DuimpSnapshotSchema()
nfe_draft_schema = NfeDraftSchema()
nfe_draft_item_schema = NfeDraftItemSchema()
nfe_xml_version_schema = NfeXmlVersionSchema()
nfe_number_sequence_schema = NfeNumberSequenceSchema()
nfe_number_sequence_list_schema = NfeNumberSequenceSchema(many=True)
upsert_nfe_number_sequence_schema = UpsertNfeNumberSequenceSchema()

client_fiscal_profile_schema = ClientFiscalProfileSchema()


def _service() -> ImportNfeService:
    return ImportNfeService(current_user=g.current_user)

def _number_sequence_service() -> NfeNumberSequenceService:
    return NfeNumberSequenceService(current_user=g.current_user)


def _json_payload() -> dict:
    payload = request.get_json(silent=True) or {}
    return payload if isinstance(payload, dict) else {}


def _validation_error_response(exc: ValidationError):
    return jsonify({"error": "validation_error", "messages": exc.messages}), 400


def _bad_request_response(exc: Exception):
    return jsonify({"error": "bad_request", "message": str(exc)}), 400


def _uuid_or_404(value: str):
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        abort(404)


@import_process_bp.get("/metadata")
@auth_required
def get_import_process_metadata():
    return jsonify(
        {
            "importProcessStatuses": ImportProcessStatus.values(),
            "importProcessSources": ImportProcessSource.values(),
            "externalProviders": ExternalProvider.values(),
            "fiscalEnvironments": FiscalEnvironment.values(),
            "externalAuthTypes": ExternalAuthType.values(),
            "externalConnectionStatuses": ExternalConnectionStatus.values(),
            "httpMethods": HttpMethod.values(),
            "nfeModels": NfeModel.values(),
            "nfePurposes": NfePurpose.values(),
            "nfeOperationTypes": NfeOperationType.values(),
            "nfeDraftStatuses": NfeDraftStatus.values(),
            "nfeXmlTypes": NfeXmlType.values(),
            "importPurposes": ImportPurpose.values(),
        }
    )


@import_process_bp.post("")
@auth_required
def create_import_process():
    try:
        payload = CreateImportProcessSchema().load(_json_payload())
        process = _service().create_import_process(payload)
        db.session.commit()
        return jsonify(import_process_schema.dump(process)), 201
    except ValidationError as exc:
        db.session.rollback()
        return _validation_error_response(exc)
    except ValueError as exc:
        db.session.rollback()
        return _bad_request_response(exc)


@import_process_bp.get("")
@auth_required
def list_import_processes():
    try:
        params = ImportProcessListQuerySchema().load(request.args)
        return jsonify(_service().list_import_processes(params))
    except ValidationError as exc:
        return _validation_error_response(exc)


@import_process_bp.get("/<process_id>")
@auth_required
def get_import_process(process_id: str):
    process_uuid = _uuid_or_404(process_id)
    service = _service()
    process = service.import_process_query_for_current_user().filter_by(id=process_uuid).first_or_404()
    return jsonify(import_process_schema.dump(process))


@import_process_bp.put("/<process_id>")
@auth_required
def update_import_process(process_id: str):
    process_uuid = _uuid_or_404(process_id)
    service = _service()
    process = service.import_process_query_for_current_user().filter_by(id=process_uuid).first_or_404()

    try:
        payload = UpdateImportProcessSchema().load(_json_payload())
        process = service.update_import_process(process, payload)
        db.session.commit()
        return jsonify(import_process_schema.dump(process))
    except ValidationError as exc:
        db.session.rollback()
        return _validation_error_response(exc)
    except ValueError as exc:
        db.session.rollback()
        return _bad_request_response(exc)


@import_process_bp.delete("/<process_id>")
@auth_required
def delete_import_process(process_id: str):
    process_uuid = _uuid_or_404(process_id)
    service = _service()
    process = service.import_process_query_for_current_user().filter_by(id=process_uuid).first_or_404()
    db.session.delete(process)
    db.session.commit()
    return "", 204


@import_process_bp.post("/<process_id>/duimp-snapshots")
@auth_required
def create_manual_duimp_snapshot(process_id: str):
    process_uuid = _uuid_or_404(process_id)
    service = _service()
    process = service.import_process_query_for_current_user().filter_by(id=process_uuid).first_or_404()

    try:
        payload = CreateManualDuimpSnapshotSchema().load(_json_payload())
        snapshot = service.create_manual_duimp_snapshot(process, payload)
        db.session.commit()
        return jsonify(duimp_snapshot_schema.dump(snapshot)), 201
    except ValidationError as exc:
        db.session.rollback()
        return _validation_error_response(exc)
    except ValueError as exc:
        db.session.rollback()
        return _bad_request_response(exc)


@import_process_bp.get("/<process_id>/duimp-snapshots")
@auth_required
def list_duimp_snapshots(process_id: str):
    process_uuid = _uuid_or_404(process_id)
    service = _service()
    service.import_process_query_for_current_user().filter_by(id=process_uuid).first_or_404()

    rows = (
        service.snapshot_query_for_current_user()
        .filter(DuimpSnapshot.import_process_id == process_uuid)
        .order_by(DuimpSnapshot.created_at.desc())
        .all()
    )
    return jsonify(duimp_snapshot_schema.dump(rows, many=True))


@import_process_bp.post("/<process_id>/nfe-draft/from-duimp")
@auth_required
def create_nfe_draft_from_duimp(process_id: str):
    process_uuid = _uuid_or_404(process_id)
    service = _service()
    process = service.import_process_query_for_current_user().filter_by(id=process_uuid).first_or_404()

    try:
        payload = CreateNfeDraftFromDuimpSchema().load(_json_payload())
        result = service.create_nfe_draft_from_duimp(process, payload)
        db.session.commit()
        return (
            jsonify(
                {
                    "draft": nfe_draft_schema.dump(result["draft"]),
                    "snapshot": duimp_snapshot_schema.dump(result["snapshot"]),
                    "validation": result["validation"],
                }
            ),
            201,
        )
    except ValidationError as exc:
        db.session.rollback()
        return _validation_error_response(exc)
    except ValueError as exc:
        db.session.rollback()
        return _bad_request_response(exc)
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": "external_integration_error", "message": str(exc)}), 502

@import_process_bp.get("/importers/<client_id>/fiscal-profile")
@auth_required
def get_importer_fiscal_profile(client_id: str):
    processor = _service()
    client_uuid = _uuid_or_404(client_id)

    try:
        profile = processor.get_importer_fiscal_profile(client_uuid)
    except ValueError as exc:
        return jsonify({"error": "not_found", "message": str(exc)}), 404

    return jsonify(client_fiscal_profile_schema.dump(profile))


@import_process_bp.put("/importers/<client_id>/fiscal-profile")
@auth_required
def upsert_importer_fiscal_profile(client_id: str):
    processor = _service()
    client_uuid = _uuid_or_404(client_id)

    payload = _json_payload()
    payload["client_id"] = client_uuid

    try:
        data = client_fiscal_profile_schema.load(payload)
        profile = processor.create_or_update_client_fiscal_profile(data)
    except ValueError as exc:
        return jsonify({"error": "bad_request", "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": "bad_request", "message": str(exc)}), 400

    db.session.commit()

    return jsonify(client_fiscal_profile_schema.dump(profile))

@import_process_bp.post("/nfe-drafts/<draft_id>/generate-access-key")
@auth_required
def generate_nfe_draft_access_key(draft_id: str):
    processor = _service()
    draft_uuid = _uuid_or_404(draft_id)

    try:
        result = processor.generate_access_key_for_draft(draft_uuid)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": "bad_request", "message": str(exc)}), 400

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


@provider_connection_bp.post("")
@auth_required
def create_provider_connection():
    try:
        payload = CreateProviderConnectionSchema().load(_json_payload())
        connection = _service().create_provider_connection(payload)
        db.session.commit()
        return jsonify(provider_connection_schema.dump(connection)), 201
    except ValidationError as exc:
        db.session.rollback()
        return _validation_error_response(exc)
    except ValueError as exc:
        db.session.rollback()
        return _bad_request_response(exc)


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
        return _validation_error_response(exc)


@provider_connection_bp.get("/<connection_id>")
@auth_required
def get_provider_connection(connection_id: str):
    connection_uuid = _uuid_or_404(connection_id)
    service = _service()
    connection = service.provider_connection_query_for_current_user().filter_by(id=connection_uuid).first_or_404()
    return jsonify(provider_connection_schema.dump(connection))


@nfe_draft_bp.get("/<draft_id>")
@auth_required
def get_nfe_draft(draft_id: str):
    draft_uuid = _uuid_or_404(draft_id)
    service = _service()
    draft = service.nfe_draft_query_for_current_user().filter_by(id=draft_uuid).first_or_404()
    detail = service.get_nfe_draft_detail(draft)
    return jsonify(
        {
            "draft": nfe_draft_schema.dump(detail["draft"]),
            "items": nfe_draft_item_schema.dump(detail["items"], many=True),
            "xmlVersions": nfe_xml_version_schema.dump(detail["xml_versions"], many=True),
        }
    )


@nfe_draft_bp.post("/<draft_id>/validate")
@auth_required
def validate_nfe_draft(draft_id: str):
    draft_uuid = _uuid_or_404(draft_id)
    service = _service()
    draft = service.nfe_draft_query_for_current_user().filter_by(id=draft_uuid).first_or_404()

    try:
        validation = service.validate_draft(draft)
        db.session.commit()
        return jsonify(validation.to_dict())
    except ValueError as exc:
        db.session.rollback()
        return _bad_request_response(exc)


@nfe_draft_bp.patch("/<draft_id>/items/<item_id>")
@auth_required
def update_nfe_draft_item(draft_id: str, item_id: str):
    draft_uuid = _uuid_or_404(draft_id)
    item_uuid = _uuid_or_404(item_id)
    service = _service()
    draft = service.nfe_draft_query_for_current_user().filter_by(id=draft_uuid).first_or_404()
    item = NfeDraftItem.query.filter_by(id=item_uuid, nfe_draft_id=draft.id).first_or_404()

    try:
        payload = UpdateNfeDraftItemSchema().load(_json_payload())
        item = service.update_draft_item(draft, item, payload)
        db.session.commit()
        return jsonify(nfe_draft_item_schema.dump(item))
    except ValidationError as exc:
        db.session.rollback()
        return _validation_error_response(exc)
    except ValueError as exc:
        db.session.rollback()
        return _bad_request_response(exc)


@nfe_draft_bp.post("/<draft_id>/generate-xml")
@auth_required
def generate_nfe_unsigned_xml(draft_id: str):
    draft_uuid = _uuid_or_404(draft_id)
    service = _service()
    draft = service.nfe_draft_query_for_current_user().filter_by(id=draft_uuid).first_or_404()

    try:
        GenerateXmlSchema().load(_json_payload())
        row = service.generate_unsigned_xml(draft)
        db.session.commit()
        return jsonify(nfe_xml_version_schema.dump(row)), 201
    except ValidationError as exc:
        db.session.rollback()
        return _validation_error_response(exc)
    except ValueError as exc:
        db.session.rollback()
        return _bad_request_response(exc)


@nfe_draft_bp.get("/<draft_id>/xml-versions")
@auth_required
def list_nfe_xml_versions(draft_id: str):
    draft_uuid = _uuid_or_404(draft_id)
    service = _service()
    draft = service.nfe_draft_query_for_current_user().filter_by(id=draft_uuid).first_or_404()
    rows = (
        NfeXmlVersion.query.filter(NfeXmlVersion.nfe_draft_id == draft.id)
        .order_by(NfeXmlVersion.version_number.desc())
        .all()
    )
    return jsonify(nfe_xml_version_schema.dump(rows, many=True))

@import_process_bp.get("/importers/<client_id>/nfe-number-sequences")
@auth_required
def list_importer_nfe_number_sequences(client_id: str):
    client_uuid = _uuid_or_404(client_id)

    query = (
        NfeNumberSequence.query
        .filter(
            NfeNumberSequence.organization_id == g.current_user.organization_id,
            NfeNumberSequence.client_id == client_uuid,
        )
        .order_by(
            NfeNumberSequence.environment.asc(),
            NfeNumberSequence.model.asc(),
            NfeNumberSequence.series.asc(),
        )
    )

    return jsonify(nfe_number_sequence_list_schema.dump(query.all()))


@import_process_bp.put("/importers/<client_id>/nfe-number-sequences")
@auth_required
def upsert_importer_nfe_number_sequence(client_id: str):
    client_uuid = _uuid_or_404(client_id)
    payload = request.get_json(force=True) or {}

    try:
        data = upsert_nfe_number_sequence_schema.load(payload)

        service = _number_sequence_service()
        sequence = service.create_or_update_nfe_number_sequence(
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

    except ValueError as exc:
        return jsonify({"error": "bad_request", "message": str(exc)}), 400

    return jsonify(nfe_number_sequence_schema.dump(sequence))