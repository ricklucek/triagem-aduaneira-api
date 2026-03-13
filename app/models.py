from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True)
    nome = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False)
    setor = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    scopes_created = db.relationship(
        "Scope", backref="created_by_user", lazy=True, foreign_keys="Scope.created_by"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class RefreshToken(db.Model):
    __tablename__ = "refresh_tokens"

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    token = db.Column(db.String(1024), nullable=False, unique=True, index=True)
    revoked = db.Column(db.Boolean, nullable=False, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Scope(db.Model):
    __tablename__ = "scopes"

    id = db.Column(db.String(64), primary_key=True)
    cnpj = db.Column(db.String(14), index=True)
    razao_social = db.Column(db.String(255), index=True)
    status = db.Column(db.String(16), nullable=False, default="draft")
    draft = db.Column(db.JSON, nullable=False, default=dict)
    version_count = db.Column(db.Integer, nullable=False, default=0)
    completeness_score = db.Column(db.Integer, nullable=False, default=0)
    created_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    responsible_user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_published_at = db.Column(db.DateTime, nullable=True)

    versions = db.relationship("ScopeVersion", backref="scope", lazy=True, cascade="all, delete")


class ScopeVersion(db.Model):
    __tablename__ = "scope_versions"

    id = db.Column(db.Integer, primary_key=True)
    scope_id = db.Column(db.String(64), db.ForeignKey("scopes.id"), nullable=False, index=True)
    version_number = db.Column(db.Integer, nullable=False)
    published_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    data = db.Column(db.JSON, nullable=False)