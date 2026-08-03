from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.extensions import Base
from app.models.utils import uuid_pk


class ClientImportTaxRule(Base):
    """Parametrização fiscal reutilizável na emissão de NF-e de importação.

    A regra guarda configuração, não um resultado fiscal definitivo. O vínculo
    ao cliente, UF, finalidade, modalidade e NCM permite selecionar a regra de
    modo determinístico e mantém a revisão tributária fora do payload diário do
    digitador.
    """

    __tablename__ = "client_import_tax_rules"

    id = uuid_pk()
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )

    name = Column(String(120), nullable=False)
    issuer_state = Column(String(2), nullable=False, index=True)
    import_purpose = Column(String(30), nullable=False, index=True)
    import_modality = Column(String(30), nullable=True, index=True)
    tax_regime = Column(String(2), nullable=True)
    # NCM completo ou prefixo. Nulo significa regra padrão para os NCMs.
    ncm_pattern = Column(String(8), nullable=True, index=True)

    priority = Column(Integer, nullable=False, default=0)
    configuration_json = Column(JSON, nullable=False)
    additional_cost_defaults = Column(JSON, nullable=True)
    transport_defaults = Column(JSON, nullable=True)
    payment_defaults = Column(JSON, nullable=True)

    active = Column(Boolean, nullable=False, default=True, index=True)
    effective_from = Column(Date, nullable=True)
    effective_until = Column(Date, nullable=True)

    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    organization = relationship("Organization")
    client = relationship("Client", foreign_keys=[client_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])

