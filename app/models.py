from datetime import datetime
import uuid

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from sqlalchemy.dialects.postgresql import UUID


class PasswordMixin:
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Admin(PasswordMixin, db.Model):
    __tablename__ = "admins"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=lambda: f"{uuid.uuid4()}")
    nome = db.Column(db.String(255), nullable=False, default="Administrador")
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    salario_minimo_vigente = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    dados_bancarios_casco = db.Column(
        db.JSON,
        nullable=False,
        default=lambda: {"banco": "", "agencia": "", "conta": ""},
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class User(PasswordMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=lambda: f"{uuid.uuid4()}")
    nome = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    role = db.Column(db.String(32), nullable=False)
    setor = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class RefreshToken(db.Model):
    __tablename__ = "refresh_tokens"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=lambda: f"{uuid.uuid4()}")
    principal_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    principal_type = db.Column(db.String(16), nullable=False, index=True)
    token = db.Column(db.String(1024), nullable=False, unique=True, index=True)
    revoked = db.Column(db.Boolean, nullable=False, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Scope(db.Model):
    __tablename__ = "scopes"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=lambda: f"{uuid.uuid4()}")
    cnpj = db.Column(db.String(14), index=True)
    razao_social = db.Column(db.String(255), index=True)
    status = db.Column(db.String(16), nullable=False, default="draft")
    draft = db.Column(db.JSON, nullable=False, default=dict)
    completeness_score = db.Column(db.Integer, nullable=False, default=0)
    created_by_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    created_by_type = db.Column(db.String(16), nullable=False, default="user")
    responsible_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_published_at = db.Column(db.DateTime, nullable=True)

    responsible_user = db.relationship("User", foreign_keys=[responsible_user_id])

class Preposto(db.Model):
    __tablename__ = "prepostos"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=lambda: f"{uuid.uuid4()}")
    nome = db.Column(db.String(255), nullable=False, index=True)
    razao_social = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    observacoes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    contatos = db.relationship(
        "PrepostoContato",
        backref="preposto",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="desc(PrepostoContato.principal), PrepostoContato.nome.asc()",
    )

    localidades = db.relationship(
        "PrepostoLocalidade",
        backref="preposto",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="PrepostoLocalidade.cidade.asc()",
    )


class PrepostoContato(db.Model):
    __tablename__ = "preposto_contatos"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=lambda: f"{uuid.uuid4()}")
    preposto_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prepostos.id"), nullable=False, index=True)

    nome = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=True, index=True)
    telefone = db.Column(db.String(64), nullable=True)
    whatsapp = db.Column(db.String(64), nullable=True)
    principal = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class PrepostoLocalidade(db.Model):
    __tablename__ = "preposto_localidades"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=lambda: f"{uuid.uuid4()}")
    preposto_id = db.Column(UUID(as_uuid=True), db.ForeignKey("prepostos.id"), nullable=False, index=True)

    cidade = db.Column(db.String(255), nullable=False, index=True)
    uf = db.Column(db.String(2), nullable=True, index=True)
    descricao_local = db.Column(db.String(255), nullable=True)
    tipo_local = db.Column(db.String(32), nullable=True)  # CIDADE, PORTO, AEROPORTO, CLIA, FRONTEIRA

    atende_importacao = db.Column(db.Boolean, nullable=False, default=False)
    atende_exportacao = db.Column(db.Boolean, nullable=False, default=False)

    valor_importacao = db.Column(db.Numeric(12, 2), nullable=True)
    valor_exportacao = db.Column(db.Numeric(12, 2), nullable=True)

    valor_importacao_descricao = db.Column(db.String(255), nullable=True)
    valor_exportacao_descricao = db.Column(db.String(255), nullable=True)

    moeda = db.Column(db.String(8), nullable=False, default="BRL")
    observacoes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.Index("ix_preposto_localidades_cidade_uf", "cidade", "uf"),
        db.Index(
            "ix_preposto_localidades_operacao",
            "cidade",
            "atende_importacao",
            "atende_exportacao",
        ),
    )