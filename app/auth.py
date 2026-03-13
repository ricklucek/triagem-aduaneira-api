import uuid
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from .extensions import db
from .models import RefreshToken, User


def _jwt_payload(user: User, token_type: str, expires_in: int) -> dict:
    now = datetime.utcnow()
    return {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }


def generate_tokens(user: User) -> dict:
    access_expires = current_app.config["JWT_ACCESS_EXPIRES_SECONDS"]
    refresh_expires = current_app.config["JWT_REFRESH_EXPIRES_SECONDS"]

    access_token = jwt.encode(
        _jwt_payload(user, "access", access_expires), current_app.config["SECRET_KEY"], algorithm="HS256"
    )
    refresh_token = jwt.encode(
        _jwt_payload(user, "refresh", refresh_expires), current_app.config["SECRET_KEY"], algorithm="HS256"
    )

    refresh_row = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(seconds=refresh_expires),
    )
    db.session.add(refresh_row)
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

        user = User.query.get(payload["sub"])
        if not user or not user.ativo:
            return jsonify({"error": "User not found or inactive"}), 401

        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @auth_required
        def wrapper(*args, **kwargs):
            if g.current_user.role not in roles:
                return jsonify({"error": "Forbidden"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator