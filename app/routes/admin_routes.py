from decimal import Decimal

from flask import Blueprint, g, jsonify, request

from ..auth import admin_required
from ..extensions import db
from ..schemas import AdminSettingsSchema

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
settings_schema = AdminSettingsSchema()


def _serialize_settings(admin) -> dict:
    return {
        "salarioMinimoVigente": float(admin.salario_minimo_vigente or 0),
        "dadosBancariosCasco": admin.dados_bancarios_casco or {"banco": "", "agencia": "", "conta": ""},
    }


@admin_bp.get("/settings")
@admin_required
def get_settings():
    return jsonify(_serialize_settings(g.current_user))


@admin_bp.put("/settings")
@admin_required
def update_settings():
    payload = settings_schema.load(request.get_json(force=True))
    g.current_user.salario_minimo_vigente = Decimal(str(payload["salarioMinimoVigente"]))
    g.current_user.dados_bancarios_casco = payload["dadosBancariosCasco"]
    db.session.commit()
    return jsonify(_serialize_settings(g.current_user))
