import uuid
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from .extensions import db
from .models import Admin, RefreshToken, User


ADMIN_ROLE = "admin"


def serialize_identity(identity) -> dict:
    if isinstance(identity, Admin):
        return {
            "id": identity.id,
            "nome": identity.nome,
            "email": identity.email,
            "role": ADMIN_ROLE,
            "setor": "Administração",
            "tipo": "admin",
        }

    return {
        "id": identity.id,
        "nome": identity.nome,
        "email": identity.email,
        "role": identity.role,
        "setor": identity.setor,
        "tipo": "user",
    }


def resolve_identity(principal_type: str, principal_id: str):
    if principal_type == "admin":
        return Admin.query.get(principal_id)
    return User.query.get(principal_id)


def _jwt_payload(identity, principal_type: str, token_type: str, expires_in: int) -> dict:
    now = datetime.utcnow()
    return {
        "sub": str(identity.id),
        "email": identity.email,
        "role": ADMIN_ROLE if principal_type == "admin" else identity.role,
        "principal_type": principal_type,
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }


def generate_tokens(identity, principal_type: str) -> dict:
    access_expires = current_app.config["JWT_ACCESS_EXPIRES_SECONDS"]
    refresh_expires = current_app.config["JWT_REFRESH_EXPIRES_SECONDS"]

    access_token = jwt.encode(
        _jwt_payload(identity, principal_type, "access", access_expires),
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )
    refresh_token = jwt.encode(
        _jwt_payload(identity, principal_type, "refresh", refresh_expires),
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )

    db.session.add(
        RefreshToken(
            principal_id=identity.id,
            principal_type=principal_type,
            token=refresh_token,
            expires_at=datetime.utcnow() + timedelta(seconds=refresh_expires),
        )
    )
    db.session.commit()

    return {"accessToken": access_token, "refreshToken": refresh_token, "expiresIn": access_expires}


def decode_token(token: str) -> dict:
    return jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])


def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "Missing Bearer token"}), 401

        token = header.split(" ", 1)[1].strip()
        try:
            payload = decode_token(token)
        except jwt.PyJWTError:
            return jsonify({"error": "Invalid token"}), 401

        if payload.get("type") != "access":
            return jsonify({"error": "Invalid access token"}), 401

        principal_type = payload.get("principal_type", "user")
        identity = resolve_identity(principal_type, payload["sub"])
        if not identity or not identity.ativo:
            return jsonify({"error": "User not found or inactive"}), 401

        g.current_user = identity
        g.current_user_type = principal_type
        g.current_identity = serialize_identity(identity)
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    @auth_required
    def wrapper(*args, **kwargs):
        if g.current_user_type != "admin":
            return jsonify({"error": "Forbidden"}), 403
        return fn(*args, **kwargs)

    return wrapper


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @auth_required
        def wrapper(*args, **kwargs):
            if g.current_user_type == "admin":
                return fn(*args, **kwargs)
            if g.current_user.role not in roles:
                return jsonify({"error": "Forbidden"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator
