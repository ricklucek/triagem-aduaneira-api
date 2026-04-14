from flask import Blueprint, g, jsonify, request

from ..auth import admin_required, auth_required
from ..extensions import db
from ..models import User
from ..schemas import UserSchema

user_bp = Blueprint("users", __name__, url_prefix="/users")
user_schema = UserSchema()
users_schema = UserSchema(many=True)
ALLOWED_ROLES = {"administrador", "comercial", "credenciamento", "operacao"}


@user_bp.get("")
@admin_required
def list_users():
    query = User.query.order_by(User.nome.asc()).filter(User.ativo == True)
    if g.current_user.organization_id:
        query = query.filter(User.organization_id == g.current_user.organization_id)
    users = query.all()

    return jsonify(UserSchema(many=True).dump(users))

@user_bp.get("/responsibles")
@auth_required
def list_responsibles():
    query = User.query.filter_by(ativo=True).order_by(User.nome.asc())
    if g.current_user.organization_id:
        query = query.filter_by(organization_id=g.current_user.organization_id)
    users = query.all()
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
        return jsonify({"ok": False, "message": "Os papeis devem ser um dos seguintes: " + ", ".join(ALLOWED_ROLES)}), 400

    if User.query.filter_by(email=payload["email"], ativo=True).first():
        return jsonify({"ok": False, "message": "Email já está em uso"}), 409

    user = User(
        nome=payload["nome"],
        email=payload["email"],
        role=role,
        setor=payload.get("setor"),
        ativo=payload.get("ativo", True),
        organization_id=g.current_user.organization_id,
    )
    if payload.get("password"):
        user.set_password(payload["password"])

    db.session.add(user)
    db.session.commit()
    return jsonify({"ok": True, "data": user_schema.dump(user)}), 201

@user_bp.put("/user/<user_id>")
@admin_required
def update_user(user_id: str):
    user = User.query.get_or_404(user_id)

    payload = request.get_json(force=True)

    user.nome = payload["nome"]
    user.email = payload["email"]
    user.setor = payload.get("setor")
    user.ativo = payload.get("ativo", True)
    if payload.get("password"):
        user.set_password(payload["password"])

    db.session.commit()
    return jsonify({"ok": True, "data": user_schema.dump(user)}), 201


@user_bp.delete("/user/<user_id>")
@admin_required
def delete_user(user_id: str):
    user = User.query.get(user_id)
    user.ativo = False
    db.session.commit()
    return jsonify({"ok": True, "message": "Usuário desativado com sucesso"}), 204


