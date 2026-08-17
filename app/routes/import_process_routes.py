from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from ..auth import auth_required
from ..extensions import db
from ..models.import_process import (
    DuimpSnapshot,
    ExternalAuthType,
    ExternalConnectionStatus,
    ExternalProvider,
    FiscalEnvironment,
    HttpMethod,
    ImportProcessSource,
    ImportProcessStatus,
    ImportPurpose,
    NfeDraft,
    NfeDraftItem,
    NfeDraftStatus,
    NfeModel,
    NfeOperationType,
    NfePurpose,
    NfeXmlType,
    NfeXmlVersion,
)
from ..schemas.import_process import (
    CreateImportProcessSchema,
    FetchDuimpSchema,
    CreateManualDuimpSnapshotSchema,
    CreateNfeDraftFromDuimpSchema,
    DuimpSnapshotSchema,
    ImportProcessListQuerySchema,
    ImportProcessSchema,
    NfeDraftItemSchema,
    NfeDraftSchema,
    NfeWorkflowStateQuerySchema,
    NfeXmlVersionSchema,
    UpdateImportProcessSchema,
)
from ..services.import_process import ImportNfeService
from .route_helpers import (
    bad_request_response,
    json_payload,
    uuid_or_404,
    validation_error_response,
)


import_process_bp = Blueprint(
    "import_processes", __name__, url_prefix="/import-processes"
)

import_process_schema = ImportProcessSchema()
duimp_snapshot_schema = DuimpSnapshotSchema()
nfe_draft_schema = NfeDraftSchema()
nfe_draft_item_schema = NfeDraftItemSchema()
nfe_xml_version_schema = NfeXmlVersionSchema()


def _service() -> ImportNfeService:
    return ImportNfeService(current_user=g.current_user)


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
        payload = CreateImportProcessSchema().load(json_payload())
        process = _service().create_import_process(payload)
        db.session.commit()
        return jsonify(import_process_schema.dump(process)), 201
    except ValidationError as exc:
        db.session.rollback()
        return validation_error_response(exc)
    except ValueError as exc:
        db.session.rollback()
        return bad_request_response(exc)


@import_process_bp.get("")
@auth_required
def list_import_processes():
    try:
        params = ImportProcessListQuerySchema().load(request.args)
        return jsonify(_service().list_import_processes(params))
    except ValidationError as exc:
        return validation_error_response(exc)


@import_process_bp.get("/<process_id>")
@auth_required
def get_import_process(process_id: str):
    process_uuid = uuid_or_404(process_id)
    service = _service()
    process = (
        service.import_process_query_for_current_user()
        .filter_by(id=process_uuid)
        .first_or_404()
    )
    return jsonify(import_process_schema.dump(process))


@import_process_bp.get("/<process_id>/nfe-workflow-state")
@auth_required
def get_nfe_workflow_state(process_id: str):
    process_uuid = uuid_or_404(process_id)
    service = _service()
    process = (
        service.import_process_query_for_current_user()
        .filter_by(id=process_uuid)
        .first_or_404()
    )

    try:
        params = NfeWorkflowStateQuerySchema().load(request.args)
        state = service.get_nfe_workflow_state(process, params)
        detail = state.get("latest_draft")
        if detail:
            state["latest_draft"] = {
                "draft": nfe_draft_schema.dump(detail["draft"]),
                "items": nfe_draft_item_schema.dump(detail["items"], many=True),
                "xmlVersions": nfe_xml_version_schema.dump(
                    detail["xml_versions"], many=True
                ),
            }
        return jsonify(state)
    except ValidationError as exc:
        return validation_error_response(exc)
    except ValueError as exc:
        return bad_request_response(exc)


@import_process_bp.put("/<process_id>")
@auth_required
def update_import_process(process_id: str):
    process_uuid = uuid_or_404(process_id)
    service = _service()
    process = (
        service.import_process_query_for_current_user()
        .filter_by(id=process_uuid)
        .first_or_404()
    )

    try:
        payload = UpdateImportProcessSchema().load(json_payload())
        process = service.update_import_process(process, payload)
        db.session.commit()
        return jsonify(import_process_schema.dump(process))
    except ValidationError as exc:
        db.session.rollback()
        return validation_error_response(exc)
    except ValueError as exc:
        db.session.rollback()
        return bad_request_response(exc)


@import_process_bp.delete("/<process_id>")
@auth_required
def delete_import_process(process_id: str):
    process_uuid = uuid_or_404(process_id)
    service = _service()
    process = (
        service.import_process_query_for_current_user()
        .filter_by(id=process_uuid)
        .first_or_404()
    )
    db.session.delete(process)
    db.session.commit()
    return "", 204


@import_process_bp.post("/<process_id>/duimp-snapshots")
@auth_required
def create_manual_duimp_snapshot(process_id: str):
    process_uuid = uuid_or_404(process_id)
    service = _service()
    process = (
        service.import_process_query_for_current_user()
        .filter_by(id=process_uuid)
        .first_or_404()
    )

    try:
        payload = CreateManualDuimpSnapshotSchema().load(json_payload())
        snapshot = service.create_manual_duimp_snapshot(process, payload)
        db.session.commit()
        return jsonify(duimp_snapshot_schema.dump(snapshot)), 201
    except ValidationError as exc:
        db.session.rollback()
        return validation_error_response(exc)
    except ValueError as exc:
        db.session.rollback()
        return bad_request_response(exc)


@import_process_bp.get("/<process_id>/duimp-snapshots")
@auth_required
def list_duimp_snapshots(process_id: str):
    process_uuid = uuid_or_404(process_id)
    service = _service()
    (
        service.import_process_query_for_current_user()
        .filter_by(id=process_uuid)
        .first_or_404()
    )

    rows = (
        service.snapshot_query_for_current_user()
        .filter(DuimpSnapshot.import_process_id == process_uuid)
        .order_by(DuimpSnapshot.created_at.desc())
        .all()
    )
    return jsonify(duimp_snapshot_schema.dump(rows, many=True))


@import_process_bp.get("/<process_id>/nfe-drafts")
@auth_required
def list_process_nfe_drafts(process_id: str):
    process_uuid = uuid_or_404(process_id)
    service = _service()
    process = (
        service.import_process_query_for_current_user()
        .filter_by(id=process_uuid)
        .first_or_404()
    )
    rows = (
        service.nfe_draft_query_for_current_user()
        .filter(NfeDraft.import_process_id == process.id)
        .order_by(
            NfeDraft.created_at.desc(),
            NfeDraft.updated_at.desc().nullslast(),
        )
        .all()
    )

    items = []
    for draft in rows:
        xml_versions = (
            NfeXmlVersion.query
            .filter(NfeXmlVersion.nfe_draft_id == draft.id)
            .order_by(
                NfeXmlVersion.version_number.desc(),
                NfeXmlVersion.generated_at.desc(),
            )
            .all()
        )
        items.append(
            {
                "id": str(draft.id),
                "status": getattr(draft.status, "value", draft.status),
                "environment": getattr(
                    draft.environment, "value", draft.environment
                ),
                "series": draft.series,
                "number": draft.number,
                "access_key": draft.access_key,
                "duimp_snapshot_id": (
                    str(draft.duimp_snapshot_id)
                    if draft.duimp_snapshot_id
                    else None
                ),
                "items_count": (
                    NfeDraftItem.query
                    .filter(NfeDraftItem.nfe_draft_id == draft.id)
                    .count()
                ),
                "validation_errors": draft.validation_errors or [],
                "validation_warnings": draft.validation_warnings or [],
                "created_at": (
                    draft.created_at.isoformat() + "Z"
                    if draft.created_at
                    else None
                ),
                "updated_at": (
                    draft.updated_at.isoformat() + "Z"
                    if draft.updated_at
                    else None
                ),
                "xml_versions": [
                    {
                        "id": str(version.id),
                        "version_number": version.version_number,
                        "xml_type": getattr(
                            version.xml_type, "value", version.xml_type
                        ),
                        "xsd_valid": version.xsd_valid,
                        "xsd_errors": version.xsd_errors or [],
                        "access_key": version.access_key,
                        "protocol_number": version.protocol_number,
                        "generated_at": (
                            version.generated_at.isoformat() + "Z"
                            if version.generated_at
                            else None
                        ),
                    }
                    for version in xml_versions
                ],
            }
        )

    return jsonify({"items": items})


@import_process_bp.post("/<process_id>/duimp/fetch")
@auth_required
def fetch_process_duimp(process_id: str):
    process_uuid = uuid_or_404(process_id)
    service = _service()
    process = (
        service.import_process_query_for_current_user()
        .filter_by(id=process_uuid)
        .first_or_404()
    )

    try:
        payload = FetchDuimpSchema().load(json_payload())
        result = service.fetch_duimp_for_process(process, payload)
        db.session.commit()
        return (
            jsonify(
                {
                    "snapshot": duimp_snapshot_schema.dump(result["snapshot"]),
                    "normalized": result["normalized"],
                }
            ),
            201,
        )
    except ValidationError as exc:
        db.session.rollback()
        return validation_error_response(exc)
    except ValueError as exc:
        db.session.rollback()
        return bad_request_response(exc)
    except Exception as exc:
        db.session.rollback()
        return jsonify(
            {"error": "external_integration_error", "message": str(exc)}
        ), 502


@import_process_bp.post("/<process_id>/nfe-draft/from-duimp")
@auth_required
def create_nfe_draft_from_duimp(process_id: str):
    process_uuid = uuid_or_404(process_id)
    service = _service()
    process = (
        service.import_process_query_for_current_user()
        .filter_by(id=process_uuid)
        .first_or_404()
    )

    try:
        payload = CreateNfeDraftFromDuimpSchema().load(json_payload())
        result = service.create_nfe_draft_from_duimp(process, payload)
        db.session.commit()
        return (
            jsonify(
                {
                    "draft": nfe_draft_schema.dump(result["draft"]),
                    "snapshot": duimp_snapshot_schema.dump(result["snapshot"]),
                    "validation": result["validation"],
                    "tax_rule": result.get("tax_rule"),
                }
            ),
            201,
        )
    except ValidationError as exc:
        db.session.rollback()
        return validation_error_response(exc)
    except ValueError as exc:
        db.session.rollback()
        return bad_request_response(exc)
    except Exception as exc:
        db.session.rollback()
        return jsonify(
            {"error": "external_integration_error", "message": str(exc)}
        ), 502
