import enum

from datetime import datetime

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Boolean, Text, Numeric, JSON, Time, UniqueConstraint
from sqlalchemy.orm import relationship

from ..extensions import Base

@enum.unique  
class ImportProcessStageEnum(str, enum.Enum):
    PRE_SHIPMENT = "pre_shipment"
    SHIPMENT_IN_TRANSIT = "shipment_in_transit"
    CUSTOMS_CLEARANCE = "customs_clearance"
    RELEASED_FOR_DELIVERY = "released_for_delivery"

@enum.unique  
class ImportProcessTagTypeEnum(str, enum.Enum):
    DTA = "dta"
    DTC = "dtc"
    LI_LPCO = "li_lpco"

@enum.unique  
class ImportProcessServiceTypeEnum(str, enum.Enum):
    CUSTOMS_CLEARANCE = "customs_clearance"
    INTERNATIONAL_FREIGHT = "international_freight"
    INTERNATIONAL_INSURANCE = "international_insurance"
    ROAD_FREIGHT = "road_freight"
    ADVISORY = "advisory"
    FINANCIAL = "financial"

@enum.unique  
class ImportProcessServiceStatusEnum(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

@enum.unique  
class ImportProcessTaskStatusEnum(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"
    BLOCKED = "blocked"

@enum.unique  
class InternationalFreightResponsibilityEnum(str, enum.Enum):
    INTERNAL = "internal"
    CLIENT = "client"
    THIRD_PARTY = "third_party"
    NOT_APPLICABLE = "not_applicable"

@enum.unique  
class FreightQuoteStatusEnum(str, enum.Enum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

class ImportProcess(Base):
    __tablename__ = "import_processes"

    id = Column(Integer, primary_key=True)

    process_number = Column(String(100), nullable=False, unique=True, index=True)

    internal_reference = Column(String(100), nullable=True, index=True)
    client_reference = Column(String(100), nullable=True, index=True)

    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )

    opened_at = Column(DateTime, nullable=False)

    current_stage = Column(
        Enum(
            ImportProcessStageEnum,
            name="import_process_stage_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ImportProcessStageEnum.PRE_SHIPMENT.value,
        index=True,
    )

    notes = Column(Text, nullable=True)

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    metadata_json = Column(JSON, nullable=False, default=dict)

    client = relationship(
        "Client",
        back_populates="import_processes",
    )

    shipments = relationship(
        "ImportProcessShipment",
        back_populates="import_process",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    freight = relationship(
        "ImportProcessFreight",
        back_populates="import_process",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )

    services = relationship(
        "ImportProcessService",
        back_populates="import_process",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    tasks = relationship(
        "ImportProcessTask",
        back_populates="import_process",
        cascade="all, delete-orphan",
        order_by="ImportProcessTask.position.asc()",
        lazy="selectin",
    )

    tags = relationship(
        "ImportProcessTag",
        back_populates="import_process",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_import_processes_client_stage", "client_id", "current_stage"),
        Index("ix_import_processes_opened_at", "opened_at"),
    )

    def __repr__(self):
        return f"<ImportProcess id={self.id} process_number={self.process_number}>"
    
class ImportProcessShipment(Base):
    __tablename__ = "import_process_shipments"

    id = Column(Integer, primary_key=True)

    import_process_id = Column(
        Integer,
        ForeignKey("import_processes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    estimated_departure_at = Column(Date, nullable=True)
    estimated_arrival_at = Column(Date, nullable=True)

    actual_departure_at = Column(Date, nullable=True)
    actual_arrival_at = Column(Date, nullable=True)

    origin = Column(String(255), nullable=True)
    destination = Column(String(255), nullable=True)

    vessel_name = Column(String(255), nullable=True)
    voyage_number = Column(String(100), nullable=True)

    master_bl = Column(String(100), nullable=True)
    house_bl = Column(String(100), nullable=True)

    container_number = Column(String(100), nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    import_process = relationship(
        "ImportProcess",
        back_populates="shipments",
    )

    __table_args__ = (
        Index(
            "ix_import_process_shipments_etd_eta",
            "estimated_departure_at",
            "estimated_arrival_at",
        ),
    )

    def __repr__(self):
        return f"<ImportProcessShipment id={self.id} import_process_id={self.import_process_id}>"
    

class ImportProcessFreight(Base):
    __tablename__ = "import_process_freights"

    id = Column(Integer, primary_key=True)

    import_process_id = Column(
        Integer,
        ForeignKey("import_processes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    international_freight_responsibility = Column(
        Enum(
            InternationalFreightResponsibilityEnum,
            name="international_freight_responsibility_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=InternationalFreightResponsibilityEnum.NOT_APPLICABLE.value,
        index=True,
    )

    quote_status = Column(
        Enum(
            FreightQuoteStatusEnum,
            name="freight_quote_status_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=FreightQuoteStatusEnum.NOT_REQUESTED.value,
        index=True,
    )

    quote_requested_at = Column(DateTime, nullable=True)
    quote_approved_at = Column(DateTime, nullable=True)
    quote_rejected_at = Column(DateTime, nullable=True)

    provider_name = Column(String(255), nullable=True)

    quoted_amount = Column(Numeric(14, 2), nullable=True)
    quoted_currency = Column(String(3), nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    import_process = relationship(
        "ImportProcess",
        back_populates="freight",
    )

    def __repr__(self):
        return f"<ImportProcessFreight id={self.id} import_process_id={self.import_process_id}>"
    
class ImportProcessService(Base):
    __tablename__ = "import_process_services"

    id = Column(Integer, primary_key=True)

    import_process_id = Column(
        Integer,
        ForeignKey("import_processes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    service_type = Column(
        Enum(
            ImportProcessServiceTypeEnum,
            name="import_process_service_type_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        index=True,
    )

    status = Column(
        Enum(
            ImportProcessServiceStatusEnum,
            name="import_process_service_status_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ImportProcessServiceStatusEnum.PENDING.value,
        index=True,
    )

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    import_process = relationship(
        "ImportProcess",
        back_populates="services",
    )

    __table_args__ = (
        UniqueConstraint(
            "import_process_id",
            "service_type",
            name="uq_import_process_service_type",
        ),
        Index(
            "ix_import_process_services_process_status",
            "import_process_id",
            "status",
        ),
    )

    def __repr__(self):
        return f"<ImportProcessService id={self.id} type={self.service_type}>"
    
class ImportProcessTask(Base):
    __tablename__ = "import_process_tasks"

    id = Column(Integer, primary_key=True)

    import_process_id = Column(
        Integer,
        ForeignKey("import_processes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    service_type = Column(
        Enum(
            ImportProcessServiceTypeEnum,
            name="import_process_task_service_type_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=False)

    description = Column(Text, nullable=True)

    status = Column(
        Enum(
            ImportProcessTaskStatusEnum,
            name="import_process_task_status_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ImportProcessTaskStatusEnum.PENDING.value,
        index=True,
    )

    position = Column(Integer, nullable=False, default=0)

    due_date = Column(Date, nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    blocked_at = Column(DateTime, nullable=True)

    blocking_reason = Column(Text, nullable=True)

    assigned_to_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    import_process = relationship(
        "ImportProcess",
        back_populates="tasks",
    )

    assigned_to_user = relationship(
        "User",
        foreign_keys=[assigned_to_user_id],
        lazy="joined",
    )

    __table_args__ = (
        Index(
            "ix_import_process_tasks_process_status",
            "import_process_id",
            "status",
        ),
        Index(
            "ix_import_process_tasks_service_status",
            "service_type",
            "status",
        ),
        Index(
            "ix_import_process_tasks_due_date",
            "due_date",
        ),
    )

    def __repr__(self):
        return f"<ImportProcessTask id={self.id} name={self.name}>"
    
class ImportProcessTag(Base):
    __tablename__ = "import_process_tags"

    id = Column(Integer, primary_key=True)

    import_process_id = Column(
        Integer,
        ForeignKey("import_processes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    tag_type = Column(
        Enum(
            ImportProcessTagTypeEnum,
            name="import_process_tag_type_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        index=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    import_process = relationship(
        "ImportProcess",
        back_populates="tags",
    )

    __table_args__ = (
        UniqueConstraint(
            "import_process_id",
            "tag_type",
            name="uq_import_process_tag_type",
        ),
    )

    def __repr__(self):
        return f"<ImportProcessTag id={self.id} tag_type={self.tag_type}>"