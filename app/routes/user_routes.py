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
    users = User.query.order_by(User.nome.asc()).filter(User.ativo == True).all()

    return jsonify(UserSchema(many=True).dump(users))

@user_bp.get("/admin")
@admin_required
def list_admin():
    admins = Admin.query.order_by(Admin.nome.asc()).filter(Admin.ativo == True).all()

    return jsonify(AdminSchema(many=True).dump(admins))


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
        return jsonify({"ok": False, "message": "Os papeis devem ser um dos seguintes: " + ", ".join(ALLOWED_ROLES)}), 400

    if User.query.filter_by(email=payload["email"], ativo=True).first() or Admin.query.filter_by(email=payload["email"], ativo=True).first():
        return jsonify({"ok": False, "message": "Email já está em uso"}), 409
    
    if role == "administrador":
        admin = Admin(nome=payload["nome"], email=payload["email"])
        admin.set_password(payload["password"])
        db.session.add(admin)
        db.session.commit()
        return jsonify({"ok": True, "data": AdminSchema().dump(admin)}), 201

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

@user_bp.delete("/admin/<admin_id>")
@admin_required
def delete_admin(admin_id: str):
    admin = Admin.query.get(admin_id)
    admin.ativo = False
    db.session.commit()
    return jsonify({"ok": True, "message": "Administrador desativado com sucesso"}), 204
