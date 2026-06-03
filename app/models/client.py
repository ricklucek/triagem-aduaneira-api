
from app.models.utils import TimestampMixin, uuid_pk

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy import Column, ForeignKey, String, Boolean, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from ..extensions import Base

class Client(TimestampMixin, Base):
    __tablename__ = "clients"

    id = uuid_pk()
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    cnpj = Column(String(14), nullable=False, index=True)
    razao_social = Column(String(255), nullable=False, index=True)
    nome_resumido = Column(String(255), nullable=True)

    inscricao_estadual = Column(String(64), nullable=True)
    inscricao_municipal = Column(String(64), nullable=True)

    endereco_completo_escritorio = Column(Text, nullable=True)
    endereco_completo_armazem = Column(Text, nullable=True)

    cnae_principal = Column(Text, nullable=True)
    cnae_secundario = Column(Text, nullable=True)
    regime_tributacao = Column(String(32), nullable=True)

    ativo = Column(Boolean, nullable=False, default=True)

    organization = relationship("Organization", back_populates="clients")

    contatos = relationship(
        "ClientContact",
        back_populates="client",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="desc(ClientContact.principal), ClientContact.nome.asc()",
    )

    scopes = relationship("Scope", back_populates="client", lazy=True)

    import_processes = relationship(
        "ImportProcess",
        back_populates="client",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "cnpj", name="uq_clients_org_cnpj"),
    )

class ClientContact(TimestampMixin, Base):
    __tablename__ = "client_contacts"

    id = uuid_pk()
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )

    nome = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    telefone = Column(String(64), nullable=True)
    whatsapp = Column(String(64), nullable=True)
    cargo_departamento = Column(String(255), nullable=True)
    principal = Column(Boolean, nullable=False, default=False)
    ativo = Column(Boolean, nullable=False, default=True)

    client = relationship("Client", back_populates="contatos")