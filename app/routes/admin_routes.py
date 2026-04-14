from flask import Blueprint, jsonify

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/settings")
def deprecated_get_settings():
    return jsonify(
        {
            "deprecated": True,
            "message": "Use GET /organizations/me/settings",
        }
    ), 410


@admin_bp.put("/settings")
def deprecated_put_settings():
    return jsonify(
        {
            "deprecated": True,
            "message": "Use PUT /organizations/me/settings",
        }
    ), 410
