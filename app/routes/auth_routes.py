from datetime import datetime

from flask import Blueprint, g, jsonify, request

from ..auth import auth_required, decode_token, generate_tokens
from ..extensions import db
from ..models import RefreshToken, User
from ..schemas import LoginSchema, RefreshSchema, UserSchema

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
login_schema = LoginSchema()
refresh_schema = RefreshSchema()
user_schema = UserSchema()


@auth_bp.post("/login")
def login():
    payload = login_schema.load(request.get_json(force=True))
    user = User.query.filter_by(email=payload["email"]).first()
    if not user or not user.check_password(payload["password"]):
        return jsonify({"error": "Invalid credentials"}), 401

    tokens = generate_tokens(user)
    return jsonify({"user": user_schema.dump(user), "tokens": tokens})


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

    user = User.query.get(decoded["sub"])
    if not user or not user.ativo:
        return jsonify({"error": "Invalid user"}), 401

    persisted.revoked = True
    db.session.commit()

    return jsonify({"tokens": generate_tokens(user)})


@auth_bp.post("/logout")
@auth_required
def logout():
    db.session.query(RefreshToken).filter_by(user_id=g.current_user.id, revoked=False).update({"revoked": True})
    db.session.commit()
    return "", 204


@auth_bp.get("/me")
@auth_required
def me():
    return jsonify(user_schema.dump(g.current_user))