from decimal import Decimal

from flask import Blueprint, g, jsonify, request

from ..auth import admin_required
from ..extensions import db
from ..models import OrganizationSetting
from ..schemas import AdminSettingsSchema

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
settings_schema = AdminSettingsSchema()
SETTINGS_KEY = "scope_fixed_info"


def _default_settings() -> dict:
    return {
        "salarioMinimoVigente": 0,
        "dadosBancariosCasco": {"banco": "", "agencia": "", "conta": ""},
    }


def _get_org_settings(org_id):
    return OrganizationSetting.query.filter_by(organization_id=org_id, key=SETTINGS_KEY).first()


@admin_bp.get("/settings")
@admin_required
def get_settings():
    if not g.current_user.organization_id:
        return jsonify(_default_settings())

    row = _get_org_settings(g.current_user.organization_id)
    return jsonify(row.value_json if row else _default_settings())


@admin_bp.put("/settings")
@admin_required
def update_settings():
    payload = settings_schema.load(request.get_json(force=True))
    if not g.current_user.organization_id:
        return jsonify({"error": "Usuário sem organização"}), 400

    serialized = {
        "salarioMinimoVigente": float(Decimal(str(payload["salarioMinimoVigente"]))),
        "dadosBancariosCasco": payload["dadosBancariosCasco"],
    }

    row = _get_org_settings(g.current_user.organization_id)
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
