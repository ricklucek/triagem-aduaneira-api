from datetime import datetime
import uuid
from flask import Blueprint, g, jsonify, request

from app.services.bootstrap_legacy_data import bootstrap_legacy_data_into_casco

from ..auth import auth_required, decode_token, generate_tokens, resolve_identity, serialize_identity
from ..extensions import db
from ..models import RefreshToken, User
from ..schemas import CreateAdminSchema, LoginSchema, RefreshSchema

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
login_schema = LoginSchema()
refresh_schema = RefreshSchema()
create_admin_schema = CreateAdminSchema()


@auth_bp.post("/login")
def login():
    payload = login_schema.load(request.get_json(force=True))

    user = User.query.filter_by(email=payload["email"]).first()
    if not user or not user.check_password(payload["password"]):
        return jsonify({"error": "Invalid credentials"}), 401
    
    return jsonify({"user": serialize_identity(user), "tokens": generate_tokens(user, "user")})


@auth_bp.post("/refresh")
def refresh():
    payload = refresh_schema.load(request.get_json(force=True))
    token = payload["refreshToken"]

    try:
        decoded = decode_token(token)
    except Exception:
        return jsonify({"error": "Invalid refresh token"}), 401

    if decoded.get("type") != "refresh":
        return jsonify({"error": "Invalid token type"}), 401

    persisted = RefreshToken.query.filter_by(token=token, revoked=False).first()
    if not persisted or persisted.expires_at < datetime.utcnow():
        return jsonify({"error": "Refresh token expired or revoked"}), 401

    identity = resolve_identity(persisted.principal_type, persisted.principal_id)
    if not identity or not identity.ativo:
        return jsonify({"error": "Invalid user"}), 401

    persisted.revoked = True
    db.session.commit()

    return jsonify({"tokens": generate_tokens(identity, persisted.principal_type)})


@auth_bp.post("/logout")
@auth_required
def logout():
    db.session.query(RefreshToken).filter_by(
        principal_id=g.current_user.id,
        principal_type=g.current_user_type,
        revoked=False,
    ).update({"revoked": True})
    db.session.commit()
    return "", 204


@auth_bp.get("/me")
@auth_required
def me():
    return jsonify(g.current_identity)

