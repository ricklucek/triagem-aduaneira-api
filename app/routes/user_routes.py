import uuid

from flask import Blueprint, jsonify, request

from ..auth import admin_required, auth_required
from ..extensions import db
from ..models import Admin, User
from ..schemas import AdminSchema, UserSchema

user_bp = Blueprint("users", __name__, url_prefix="/users")
user_schema = UserSchema()
users_schema = UserSchema(many=True)
ALLOWED_ROLES = {"administrador", "comercial", "credenciamento", "operacao"}


@user_bp.get("")
@admin_required
def list_users():
    users = User.query.order_by(User.nome.asc()).all()
    return jsonify(users_schema.dump(users))


@user_bp.get("/responsibles")
@auth_required
def list_responsibles():
    users = User.query.filter_by(ativo=True).order_by(User.nome.asc()).all()
    return jsonify(
        [
            {
                "id": user.id,
                "nome": user.nome,
                "email": user.email,
                "role": user.role,
                "setor": user.setor,
            }
            for user in users
        ]
    )


@user_bp.post("")
@admin_required
def create_user():
    payload = request.get_json(force=True)
    role = payload.get("role")
    if role not in ALLOWED_ROLES:
        return jsonify({"error": "role must be one of comercial, credenciamento, operacao"}), 400

    if User.query.filter_by(email=payload["email"]).first() or Admin.query.filter_by(email=payload["email"]).first():
        return jsonify({"error": "Email already in use"}), 409
    
    if role == "administrador":
        admin = Admin(nome=payload["nome"], email=payload["email"])
        admin.set_password(payload["password"])
        db.session.add(admin)
        db.session.commit()
        return jsonify(AdminSchema().dump(admin)), 201

    user = User(
        nome=payload["nome"],
        email=payload["email"],
        role=role,
        setor=payload.get("setor"),
        ativo=payload.get("ativo", True),
    )
    user.set_password(payload["password"])

    db.session.add(user)
    db.session.commit()
    return jsonify(user_schema.dump(user)), 201


@user_bp.delete("/user/<user_id>")
@admin_required
def delete_user(user_id: str):
    user = User.query.get(user_id)
    user.ativo = False
    db.session.commit()
    return "", 204

@user_bp.delete("/admin/<admin_id>")
@admin_required
def delete_admin(admin_id: str):
    admin = Admin.query.get(admin_id)
    admin.ativo = False
    db.session.commit()
    return "", 204
