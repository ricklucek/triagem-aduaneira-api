from decimal import Decimal

from flask import Blueprint, g, jsonify, request

from ..auth import admin_required, auth_required
from ..extensions import db
from ..models import Organization, OrganizationSetting
from ..schemas import OrganizationFixedInfoSchema, OrganizationSchema

organization_bp = Blueprint("organizations", __name__, url_prefix="/organizations")
organization_schema = OrganizationSchema()
fixed_info_schema = OrganizationFixedInfoSchema()
SETTINGS_KEY = "scope_fixed_info"


def _default_fixed_info() -> dict:
    return {
        "salarioMinimoVigente": 0,
        "dadosBancariosCasco": {"banco": "", "agencia": "", "conta": ""},
    }


def _get_settings(org_id):
    return OrganizationSetting.query.filter_by(organization_id=org_id, key=SETTINGS_KEY).first()


@organization_bp.get("/me")
@auth_required
def get_my_organization():
    if not g.current_user.organization_id:
        return jsonify({"error": "Usuário sem organização"}), 400

    org = Organization.query.get_or_404(g.current_user.organization_id)
    setting = _get_settings(org.id)

    return jsonify(
        {
            "organization": organization_schema.dump(org),
            "fixedInfo": setting.value_json if setting else _default_fixed_info(),
        }
    )


@organization_bp.get("/me/settings")
@auth_required
def get_my_organization_settings():
    if not g.current_user.organization_id:
        return jsonify({"error": "Usuário sem organização"}), 400

    setting = _get_settings(g.current_user.organization_id)
    return jsonify(setting.value_json if setting else _default_fixed_info())


@organization_bp.put("/me/settings")
@admin_required
def update_my_organization_settings():
    if not g.current_user.organization_id:
        return jsonify({"error": "Usuário sem organização"}), 400

    payload = fixed_info_schema.load(request.get_json(force=True))
    serialized = {
        "salarioMinimoVigente": float(Decimal(str(payload["salarioMinimoVigente"]))),
        "dadosBancariosCasco": payload["dadosBancariosCasco"],
    }

    row = _get_settings(g.current_user.organization_id)
    if not row:
        row = OrganizationSetting(
            organization_id=g.current_user.organization_id,
            key=SETTINGS_KEY,
            value_json=serialized,
            updated_by_user_id=g.current_user.id,
        )
        db.session.add(row)
    else:
        row.value_json = serialized
        row.updated_by_user_id = g.current_user.id

    db.session.commit()

    return jsonify(serialized)
