import uuid

from flask import Blueprint, jsonify, request

from ..auth import roles_required
from ..extensions import db
from ..models import User
from ..schemas import UserSchema

user_bp = Blueprint("users", __name__, url_prefix="/users")
user_schema = UserSchema()
users_schema = UserSchema(many=True)
ALLOWED_ROLES = {"comercial", "credenciamento", "operacao"}


@user_bp.get("")
@roles_required("admin")
def list_users():
    users = User.query.order_by(User.nome.asc()).all()
    return jsonify(users_schema.dump(users))


@user_bp.post("")
@roles_required("admin")
def create_user():
    payload = request.get_json(force=True)
    role = payload.get("role")
    if role not in ALLOWED_ROLES:
        return jsonify({"error": "role must be one of comercial, credenciamento, operacao"}), 400

    user = User(
        nome=payload["nome"],
        email=payload["email"],
        role=role,
        setor=payload.get("setor"),
        ativo=True,
    )
    user.set_password(payload["password"])

    db.session.add(user)
    db.session.commit()
    return jsonify(user_schema.dump(user)), 201