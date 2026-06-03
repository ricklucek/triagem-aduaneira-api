from datetime import datetime

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy import Column, ForeignKey, Index, String, Boolean, Text, Numeric, JSON, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.utils import TimestampMixin, uuid_pk

from ..extensions import Base

class Preposto(TimestampMixin, Base):
    __tablename__ = "prepostos"

    id = uuid_pk()
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )

    nome = Column(String(255), nullable=False, index=True)
    razao_social = Column(String(255), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    observacoes = Column(Text, nullable=True)

    organization = relationship("Organization", back_populates="prepostos")

    contatos = relationship(
        "PrepostoContato",
        back_populates="preposto",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="desc(PrepostoContato.principal), PrepostoContato.nome.asc()",
    )

    localidades = relationship(
        "PrepostoLocalidade",
        back_populates="preposto",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="PrepostoLocalidade.cidade.asc()",
    )

    scope_links = relationship(
        "ScopePreposto",
        back_populates="preposto",
        lazy=True,
        cascade="all, delete-orphan",
    )


class PrepostoContato(TimestampMixin, Base):
    __tablename__ = "preposto_contatos"

    id = uuid_pk()
    preposto_id = Column(
        UUID(as_uuid=True),
        ForeignKey("prepostos.id"),
        nullable=False,
        index=True,
    )

    nome = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    telefone = Column(String(64), nullable=True)
    whatsapp = Column(String(64), nullable=True)
    principal = Column(Boolean, nullable=False, default=False)

    preposto = relationship("Preposto", back_populates="contatos")


class PrepostoLocalidade(TimestampMixin, Base):
    __tablename__ = "preposto_localidades"

    id = uuid_pk()
    preposto_id = Column(
        UUID(as_uuid=True),
        ForeignKey("prepostos.id"),
        nullable=False,
        index=True,
    )

    cidade = Column(String(255), nullable=False, index=True)
    uf = Column(String(2), nullable=True, index=True)
    descricao_local = Column(String(255), nullable=True)
    tipo_local = Column(String(32), nullable=True)  # CIDADE, PORTO, AEROPORTO, CLIA, FRONTEIRA

    atende_importacao = Column(Boolean, nullable=False, default=False)
    atende_exportacao = Column(Boolean, nullable=False, default=False)

    valor_importacao = Column(Numeric(12, 2), nullable=True)
    valor_exportacao = Column(Numeric(12, 2), nullable=True)

    valor_importacao_descricao = Column(String(255), nullable=True)
    valor_exportacao_descricao = Column(String(255), nullable=True)

    moeda = Column(String(8), nullable=False, default="BRL")
    observacoes = Column(Text, nullable=True)

    preposto = relationship("Preposto", back_populates="localidades")

    __table_args__ = (
        Index("ix_preposto_localidades_cidade_uf", "cidade", "uf"),
        Index(
            "ix_preposto_localidades_operacao",
            "cidade",
            "atende_importacao",
            "atende_exportacao",
        ),
    )


class ScopePreposto(TimestampMixin, Base):
    __tablename__ = "scope_prepostos"

    id = uuid_pk()
    scope_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scopes.id"),
        nullable=False,
        index=True,
    )
    preposto_id = Column(
        UUID(as_uuid=True),
        ForeignKey("prepostos.id"),
        nullable=False,
        index=True,
    )

    operation_type = Column(String(20), nullable=False)  # IMPORTACAO / EXPORTACAO
    enabled = Column(Boolean, nullable=False, default=False)

    valor = Column(Numeric(12, 2), nullable=True)
    incluso_no_desembaraco_casco = Column(Boolean, nullable=True)

    extra_data = Column(JSON, nullable=False, default=dict)

    scope = relationship("Scope")
    preposto = relationship("Preposto", back_populates="scope_links")

    __table_args__ = (
        UniqueConstraint("scope_id", "preposto_id", "operation_type", name="uq_scope_preposto_unique"),
    )