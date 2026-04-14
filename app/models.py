from datetime import datetime
import uuid

from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import UniqueConstraint

from .extensions import db

class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=True,
    )


class PasswordMixin:
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


def uuid_pk():
    return db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

class Organization(TimestampMixin, db.Model):
    __tablename__ = "organizations"

    id = uuid_pk()
    nome = db.Column(db.String(255), nullable=False, unique=True, index=True)
    slug = db.Column(db.String(100), nullable=False, unique=True, index=True)
    cnpj = db.Column(db.String(14), nullable=True, unique=True, index=True)
    email = db.Column(db.String(255), nullable=True)
    telefone = db.Column(db.String(64), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    users = db.relationship("User", back_populates="organization", lazy=True)
    clients = db.relationship("Client", back_populates="organization", lazy=True)
    scopes = db.relationship("Scope", back_populates="organization", lazy=True)
    prepostos = db.relationship("Preposto", back_populates="organization", lazy=True)
    settings = db.relationship(
        "OrganizationSetting",
        back_populates="organization",
        lazy=True,
        cascade="all, delete-orphan",
    )


class OrganizationSetting(TimestampMixin, db.Model):
    __tablename__ = "organization_settings"

    id = uuid_pk()
    organization_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    key = db.Column(db.String(100), nullable=False, index=True)
    value_json = db.Column(db.JSON, nullable=False, default=dict)
    updated_by_user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    organization = db.relationship("Organization", back_populates="settings")
    updated_by_user = db.relationship("User", foreign_keys=[updated_by_user_id])

    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_org_settings_org_key"),
    )


class User(PasswordMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = uuid_pk()
    organization_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )

    nome = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)

    role = db.Column(db.String(32), nullable=False, default="user")
    setor = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    organization = db.relationship("Organization", back_populates="users")
    admin_profile = db.relationship(
        "AdminProfile",
        uselist=False,
        back_populates="user",
        cascade="all, delete-orphan",
    )

    assigned_scopes = db.relationship(
        "ScopeAssignment",
        foreign_keys="ScopeAssignment.user_id",
        back_populates="user",
        lazy=True,
    )


class AdminProfile(TimestampMixin, db.Model):
    __tablename__ = "admin_profiles"

    id = uuid_pk()
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id"),
        nullable=True,
        unique=True,
        index=True,
    )

    is_super_admin = db.Column(db.Boolean, nullable=False, default=False)
    can_manage_users = db.Column(db.Boolean, nullable=False, default=True)
    can_manage_settings = db.Column(db.Boolean, nullable=False, default=True)
    can_manage_billing = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship("User", back_populates="admin_profile")


class RefreshToken(db.Model):
    __tablename__ = "refresh_tokens"

    id = uuid_pk()
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    token = db.Column(db.String(1024), nullable=False, unique=True, index=True)
    revoked = db.Column(db.Boolean, nullable=False, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User")


class Client(TimestampMixin, db.Model):
    __tablename__ = "clients"

    id = uuid_pk()
    organization_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    cnpj = db.Column(db.String(14), nullable=False, index=True)
    razao_social = db.Column(db.String(255), nullable=False, index=True)
    nome_resumido = db.Column(db.String(255), nullable=True)

    inscricao_estadual = db.Column(db.String(64), nullable=True)
    inscricao_municipal = db.Column(db.String(64), nullable=True)

    endereco_completo_escritorio = db.Column(db.Text, nullable=True)
    endereco_completo_armazem = db.Column(db.Text, nullable=True)

    cnae_principal = db.Column(db.Text, nullable=True)
    cnae_secundario = db.Column(db.Text, nullable=True)
    regime_tributacao = db.Column(db.String(32), nullable=True)

    ativo = db.Column(db.Boolean, nullable=False, default=True)

    organization = db.relationship("Organization", back_populates="clients")

    contatos = db.relationship(
        "ClientContact",
        back_populates="client",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="desc(ClientContact.principal), ClientContact.nome.asc()",
    )

    scopes = db.relationship("Scope", back_populates="client", lazy=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "cnpj", name="uq_clients_org_cnpj"),
    )


class ClientContact(TimestampMixin, db.Model):
    __tablename__ = "client_contacts"

    id = uuid_pk()
    client_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )

    nome = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=True, index=True)
    telefone = db.Column(db.String(64), nullable=True)
    whatsapp = db.Column(db.String(64), nullable=True)
    cargo_departamento = db.Column(db.String(255), nullable=True)
    principal = db.Column(db.Boolean, nullable=False, default=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    client = db.relationship("Client", back_populates="contatos")

class Scope(TimestampMixin, db.Model):
    __tablename__ = "scopes"

    id = uuid_pk()

    organization_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )

    client_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("clients.id"),
        nullable=True,
        index=True,
    )

    status = db.Column(db.String(16), nullable=False, default="draft", index=True)

    # Compatibilidade com o front atual
    draft = db.Column(db.JSON, nullable=False, default=dict)

    # snapshot opcional da última publicação
    published_snapshot = db.Column(db.JSON, nullable=True)

    completeness_score = db.Column(db.Integer, nullable=False, default=0)
    version = db.Column(db.Integer, nullable=True, default=1)

    created_by_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    # Atalho temporário útil para listagem, mas sem impedir assignments por papel
    responsible_user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    last_published_at = db.Column(db.DateTime, nullable=True)

    organization = db.relationship("Organization", back_populates="scopes")
    client = db.relationship("Client", back_populates="scopes")

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    responsible_user = db.relationship("User", foreign_keys=[responsible_user_id])

    assignments = db.relationship(
        "ScopeAssignment",
        back_populates="scope",
        lazy=True,
        cascade="all, delete-orphan",
    )

    services = db.relationship(
        "ScopeService",
        back_populates="scope",
        lazy=True,
        cascade="all, delete-orphan",
    )

    versions = db.relationship(
        "ScopeVersion",
        back_populates="scope",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="desc(ScopeVersion.version_number)",
    )


class ScopeVersion(db.Model):
    __tablename__ = "scope_versions"

    id = uuid_pk()
    scope_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("scopes.id"),
        nullable=False,
        index=True,
    )
    version_number = db.Column(db.Integer, nullable=False)
    draft_snapshot = db.Column(db.JSON, nullable=False)
    published_snapshot = db.Column(db.JSON, nullable=True)

    created_by_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    scope = db.relationship("Scope", back_populates="versions")
    created_by = db.relationship("User")

    __table_args__ = (
        UniqueConstraint("scope_id", "version_number", name="uq_scope_versions_scope_version"),
    )


class ScopeAssignment(TimestampMixin, db.Model):
    __tablename__ = "scope_assignments"

    id = uuid_pk()
    scope_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("scopes.id"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    # Ex.: RESPONSAVEL_COMERCIAL, ANALISTA_DA_IMPORT, ANALISTA_AE_IMPORT, ANALISTA_DA_EXPORT
    role = db.Column(db.String(64), nullable=False, index=True)

    active = db.Column(db.Boolean, nullable=False, default=True)
    starts_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=True)

    scope = db.relationship("Scope", back_populates="assignments")
    user = db.relationship("User", back_populates="assigned_scopes")

    __table_args__ = (
        db.Index("ix_scope_assignments_scope_role_active", "scope_id", "role", "active"),
    )


# =========================================================
# CATÁLOGO DE SERVIÇOS
# =========================================================

class ServiceCatalog(TimestampMixin, db.Model):
    __tablename__ = "service_catalog"

    id = uuid_pk()
    organization_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    code = db.Column(db.String(100), nullable=False, index=True)
    nome = db.Column(db.String(255), nullable=False)
    operation_type = db.Column(db.String(20), nullable=False)  # IMPORTACAO, EXPORTACAO, AMBOS
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    organization = db.relationship("Organization")
    scope_services = db.relationship("ScopeService", back_populates="service_catalog", lazy=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_service_catalog_org_code"),
    )


class ScopeService(TimestampMixin, db.Model):
    __tablename__ = "scope_services"

    id = uuid_pk()
    scope_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("scopes.id"),
        nullable=False,
        index=True,
    )
    service_catalog_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("service_catalog.id"),
        nullable=False,
        index=True,
    )

    enabled = db.Column(db.Boolean, nullable=False, default=False)

    # FIXO, OUTRO, PERCENTUAL, CASO_A_CASO
    pricing_type = db.Column(db.String(30), nullable=True)
    amount = db.Column(db.Numeric(12, 2), nullable=True)
    currency = db.Column(db.String(8), nullable=False, default="BRL")

    responsible_user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    # detalhes variáveis de cada serviço
    extra_data = db.Column(db.JSON, nullable=False, default=dict)

    scope = db.relationship("Scope", back_populates="services")
    service_catalog = db.relationship("ServiceCatalog", back_populates="scope_services")
    responsible_user = db.relationship("User")

    __table_args__ = (
        UniqueConstraint("scope_id", "service_catalog_id", name="uq_scope_service_unique"),
    )


class Preposto(TimestampMixin, db.Model):
    __tablename__ = "prepostos"

    id = uuid_pk()
    organization_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )

    nome = db.Column(db.String(255), nullable=False, index=True)
    razao_social = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    observacoes = db.Column(db.Text, nullable=True)

    organization = db.relationship("Organization", back_populates="prepostos")

    contatos = db.relationship(
        "PrepostoContato",
        back_populates="preposto",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="desc(PrepostoContato.principal), PrepostoContato.nome.asc()",
    )

    localidades = db.relationship(
        "PrepostoLocalidade",
        back_populates="preposto",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="PrepostoLocalidade.cidade.asc()",
    )

    scope_links = db.relationship(
        "ScopePreposto",
        back_populates="preposto",
        lazy=True,
        cascade="all, delete-orphan",
    )


class PrepostoContato(TimestampMixin, db.Model):
    __tablename__ = "preposto_contatos"

    id = uuid_pk()
    preposto_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("prepostos.id"),
        nullable=False,
        index=True,
    )

    nome = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=True, index=True)
    telefone = db.Column(db.String(64), nullable=True)
    whatsapp = db.Column(db.String(64), nullable=True)
    principal = db.Column(db.Boolean, nullable=False, default=False)

    preposto = db.relationship("Preposto", back_populates="contatos")


class PrepostoLocalidade(TimestampMixin, db.Model):
    __tablename__ = "preposto_localidades"

    id = uuid_pk()
    preposto_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("prepostos.id"),
        nullable=False,
        index=True,
    )

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

    preposto = db.relationship("Preposto", back_populates="localidades")

    __table_args__ = (
        db.Index("ix_preposto_localidades_cidade_uf", "cidade", "uf"),
        db.Index(
            "ix_preposto_localidades_operacao",
            "cidade",
            "atende_importacao",
            "atende_exportacao",
        ),
    )


class ScopePreposto(TimestampMixin, db.Model):
    __tablename__ = "scope_prepostos"

    id = uuid_pk()
    scope_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("scopes.id"),
        nullable=False,
        index=True,
    )
    preposto_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("prepostos.id"),
        nullable=False,
        index=True,
    )

    operation_type = db.Column(db.String(20), nullable=False)  # IMPORTACAO / EXPORTACAO
    enabled = db.Column(db.Boolean, nullable=False, default=False)

    valor = db.Column(db.Numeric(12, 2), nullable=True)
    incluso_no_desembaraco_casco = db.Column(db.Boolean, nullable=True)

    extra_data = db.Column(db.JSON, nullable=False, default=dict)

    scope = db.relationship("Scope")
    preposto = db.relationship("Preposto", back_populates="scope_links")

    __table_args__ = (
        UniqueConstraint("scope_id", "preposto_id", "operation_type", name="uq_scope_preposto_unique"),
    )