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
    NfeDraftStatus,
    NfeModel,
    NfeOperationType,
    NfePurpose,
    NfeXmlType,
)
from ..schemas.import_process import (
    CreateImportProcessSchema,
    FetchDuimpSchema,
    CreateManualDuimpSnapshotSchema,
    CreateNfeDraftFromDuimpSchema,
    DuimpSnapshotSchema,
    ImportProcessListQuerySchema,
    ImportProcessSchema,
    NfeDraftSchema,
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
