from flask import Blueprint, jsonify, request
from marshmallow import ValidationError

from ..auth import auth_required
from ..schemas.fiscal_reference import (
    CountryReferenceQuerySchema,
    FiscalCountrySchema,
    FiscalMunicipalitySchema,
    MunicipalityReferenceQuerySchema,
)
from ..services.fiscal_reference import FiscalReferenceService
from .route_helpers import validation_error_response


fiscal_reference_bp = Blueprint(
    "fiscal_reference",
    __name__,
    url_prefix="/fiscal-reference",
)

municipality_query_schema = MunicipalityReferenceQuerySchema()
country_query_schema = CountryReferenceQuerySchema()
municipality_list_schema = FiscalMunicipalitySchema(many=True)
country_list_schema = FiscalCountrySchema(many=True)


@fiscal_reference_bp.get("/municipalities")
@auth_required
def list_fiscal_municipalities():
    try:
        params = municipality_query_schema.load(request.args)
    except ValidationError as exc:
        return validation_error_response(exc)

    rows = FiscalReferenceService.search_municipalities(
        query=params["q"],
        state=params["state"],
        limit=params["limit"],
    )
    return jsonify(
        {
            "items": municipality_list_schema.dump(rows),
            "total": len(rows),
            "limit": params["limit"],
            "q": params["q"],
            "state": (params["state"] or "").upper() or None,
        }
    )


@fiscal_reference_bp.get("/countries")
@auth_required
def list_fiscal_countries():
    try:
        params = country_query_schema.load(request.args)
    except ValidationError as exc:
        return validation_error_response(exc)

    rows = FiscalReferenceService.search_countries(
        query=params["q"],
        active_on=params["active_on"],
        limit=params["limit"],
    )
    return jsonify(
        {
            "items": country_list_schema.dump(rows),
            "total": len(rows),
            "limit": params["limit"],
            "q": params["q"],
            "active_on": params["active_on"].isoformat(),
        }
    )
