from flask import Blueprint, current_app, g, jsonify
from marshmallow import ValidationError

from app.auth import admin_required, auth_required
from app.extensions import db
from app.schemas.fiscal_certificate import RegisterFiscalCertificateSchema
from app.services.fiscal_certificate import (
    DefaultCertificateVault,
    FiscalCertificateError,
)
from app.services.fiscal_certificate_registry import FiscalCertificateRegistry

from .route_helpers import (
    json_payload,
    uuid_or_404,
    validation_error_response,
)


fiscal_certificate_bp = Blueprint(
    "fiscal_certificates",
    __name__,
    url_prefix="/clients",
)
register_schema = RegisterFiscalCertificateSchema()


def _service() -> FiscalCertificateRegistry:
    return FiscalCertificateRegistry(
        current_user=g.current_user,
        vault=(
            current_app.config.get("NFE_CERTIFICATE_VAULT")
            or DefaultCertificateVault()
        ),
    )


def _error_response(exc: FiscalCertificateError, status_code: int = 400):
    return (
        jsonify(
            {
                "error": "fiscal_certificate_error",
                "message": str(exc),
            }
        ),
        status_code,
    )


@fiscal_certificate_bp.get("/<client_id>/fiscal-certificates")
@auth_required
def list_fiscal_certificates(client_id: str):
    client_uuid = uuid_or_404(client_id)
    try:
        rows = _service().list_for_client(client_uuid)
    except FiscalCertificateError as exc:
        return _error_response(exc, 404)
    return jsonify([_service().public_data(row) for row in rows])


@fiscal_certificate_bp.post("/<client_id>/fiscal-certificates")
@admin_required
def register_fiscal_certificate(client_id: str):
    client_uuid = uuid_or_404(client_id)
    try:
        data = register_schema.load(json_payload())
        row = _service().register(client_id=client_uuid, **data)
        db.session.commit()
    except ValidationError as exc:
        db.session.rollback()
        return validation_error_response(exc)
    except FiscalCertificateError as exc:
        db.session.rollback()
        return _error_response(exc)
    return jsonify(_service().public_data(row)), 201


@fiscal_certificate_bp.post(
    "/<client_id>/fiscal-certificates/<certificate_id>/validate"
)
@admin_required
def validate_fiscal_certificate(client_id: str, certificate_id: str):
    client_uuid = uuid_or_404(client_id)
    certificate_uuid = uuid_or_404(certificate_id)
    service = _service()
    try:
        row = service.validate(certificate_uuid, client_id=client_uuid)
        db.session.commit()
    except FiscalCertificateError as exc:
        db.session.commit()
        return _error_response(exc, 422)
    return jsonify({"valid": True, **service.public_data(row)})


@fiscal_certificate_bp.post(
    "/<client_id>/fiscal-certificates/<certificate_id>/activate"
)
@admin_required
def activate_fiscal_certificate(client_id: str, certificate_id: str):
    client_uuid = uuid_or_404(client_id)
    certificate_uuid = uuid_or_404(certificate_id)
    service = _service()
    try:
        row = service.activate(certificate_uuid, client_id=client_uuid)
        db.session.commit()
    except FiscalCertificateError as exc:
        db.session.rollback()
        return _error_response(exc, 422)
    return jsonify(service.public_data(row))
