from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.models import (
    ImportProcess,
    ImportProcessShipment,
    ImportProcessFreight,
    ImportProcessService,
    ImportProcessTask,
    ImportProcessTaskChecklistItem,
    ImportProcessTag,
)
from app.models.process import ImportProcessStageEnum
from app.schemas.client import ClientSchema

from marshmallow_enum import EnumField

IMPORT_PROCESS_STAGES = (
    "pre_shipment",
    "shipment_in_transit",
    "customs_clearance",
    "released_for_delivery",
)

IMPORT_PROCESS_TAG_TYPES = (
    "dta",
    "dtc",
    "li_lpco",
)

IMPORT_PROCESS_SERVICE_TYPES = (
    "customs_clearance",
    "international_freight",
    "international_insurance",
    "road_freight",
    "advisory",
    "financial",
)

IMPORT_PROCESS_SERVICE_STATUSES = (
    "pending",
    "in_progress",
    "completed",
    "cancelled",
)

IMPORT_PROCESS_TASK_STATUSES = (
    "pending",
    "active",
    "done",
    "blocked",
)

INTERNATIONAL_FREIGHT_RESPONSIBILITIES = (
    "internal",
    "client",
    "third_party",
    "not_applicable",
)

FREIGHT_QUOTE_STATUSES = (
    "not_requested",
    "pending",
    "approved",
    "rejected",
    "cancelled",
)

IMPORT_PROCESS_SERVICE_RESPONSIBILITIES = (
    "internal",
    "client",
    "third_party",
    "not_applicable",
)

class ImportProcessTaskChecklistItemSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ImportProcessTaskChecklistItem
        load_instance = True
        include_fk = True

class ImportProcessShipmentSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ImportProcessShipment
        load_instance = True
        include_fk = True


class ImportProcessFreightSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ImportProcessFreight
        load_instance = True
        include_fk = True


class ImportProcessServiceSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ImportProcessService
        load_instance = True
        include_fk = True


class ImportProcessTaskSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ImportProcessTask
        load_instance = True
        include_fk = True

    checklist_items = fields.Nested(
        ImportProcessTaskChecklistItemSchema,
        many=True,
        dump_only=True,
    )


class ImportProcessTagSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ImportProcessTag
        load_instance = True
        include_fk = True

class ImportProcessSchema(SQLAlchemyAutoSchema):
    
    class Meta:
        model = ImportProcess
        load_instance = True
        include_fk = True

    shipments = fields.Nested(
        ImportProcessShipmentSchema,
        many=True,
        dump_only=True,
    )

    freight = fields.Nested(
        ImportProcessFreightSchema,
        dump_only=True,
        allow_none=True,
    )

    services = fields.Nested(
        ImportProcessServiceSchema,
        many=True,
        dump_only=True,
    )

    tasks = fields.Nested(
        ImportProcessTaskSchema,
        many=True,
        dump_only=True,
    )

    tags = fields.Nested(
        ImportProcessTagSchema,
        many=True,
        dump_only=True,
    )

    client = fields.Nested(
        ClientSchema,
        dump_only=True,
    )

    current_stage = EnumField(ImportProcessStageEnum, by_value=True)

class ImportProcessListQuerySchema(Schema):
    q = fields.String(required=False)

    process_number = fields.String(required=False)
    internal_reference = fields.String(required=False)
    client_reference = fields.String(required=False)

    client_id = fields.Integer(required=False)

    current_stage = fields.String(
        required=False,
        validate=validate.OneOf(IMPORT_PROCESS_STAGES),
    )

    service_type = fields.String(
        required=False,
        validate=validate.OneOf(IMPORT_PROCESS_SERVICE_TYPES),
    )

    service_status = fields.String(
        required=False,
        validate=validate.OneOf(IMPORT_PROCESS_SERVICE_STATUSES),
    )

    task_status = fields.String(
        required=False,
        validate=validate.OneOf(IMPORT_PROCESS_TASK_STATUSES),
    )

    tag_type = fields.String(
        required=False,
        validate=validate.OneOf(IMPORT_PROCESS_TAG_TYPES),
    )

    international_freight_responsibility = fields.String(
        required=False,
        validate=validate.OneOf(INTERNATIONAL_FREIGHT_RESPONSIBILITIES),
    )

    quote_status = fields.String(
        required=False,
        validate=validate.OneOf(FREIGHT_QUOTE_STATUSES),
    )

    opened_from = fields.Date(required=False)
    opened_to = fields.Date(required=False)

    eta_from = fields.Date(required=False)
    eta_to = fields.Date(required=False)

    etd_from = fields.Date(required=False)
    etd_to = fields.Date(required=False)

    assigned_to_user_id = fields.Integer(required=False)

    limit = fields.Integer(
        load_default=20,
        validate=validate.Range(min=1, max=200),
    )

    offset = fields.Integer(
        load_default=0,
        validate=validate.Range(min=0),
    )

    sort_by = fields.String(
        load_default="opened_at",
        validate=validate.OneOf(
            (
                "opened_at",
                "process_number",
                "current_stage",
                "estimated_departure_at",
                "estimated_arrival_at",
                "created_at",
                "updated_at",
            )
        ),
    )

    sort_order = fields.String(
        load_default="desc",
        validate=validate.OneOf(("asc", "desc")),
    )


class ImportProcessShipmentCreateSchema(Schema):
    estimated_departure_at = fields.Date(allow_none=True, required=False)
    estimated_arrival_at = fields.Date(allow_none=True, required=False)

    actual_departure_at = fields.Date(allow_none=True, required=False)
    actual_arrival_at = fields.Date(allow_none=True, required=False)

    origin = fields.String(allow_none=True, required=False)
    destination = fields.String(allow_none=True, required=False)

    vessel_name = fields.String(allow_none=True, required=False)
    voyage_number = fields.String(allow_none=True, required=False)

    master_bl = fields.String(allow_none=True, required=False)
    house_bl = fields.String(allow_none=True, required=False)

    container_number = fields.String(allow_none=True, required=False)

    notes = fields.String(allow_none=True, required=False)

class ImportProcessFreightCreateSchema(Schema):
    international_freight_responsibility = fields.String(
        load_default="not_applicable",
        validate=validate.OneOf(INTERNATIONAL_FREIGHT_RESPONSIBILITIES),
    )

    quote_status = fields.String(
        load_default="not_requested",
        validate=validate.OneOf(FREIGHT_QUOTE_STATUSES),
    )

    quote_requested_at = fields.DateTime(allow_none=True, required=False)
    quote_approved_at = fields.DateTime(allow_none=True, required=False)
    quote_rejected_at = fields.DateTime(allow_none=True, required=False)

    provider_name = fields.String(allow_none=True, required=False)

    quoted_amount = fields.Decimal(
        as_string=True,
        places=2,
        allow_none=True,
        required=False,
    )

    quoted_currency = fields.String(
        allow_none=True,
        required=False,
        validate=validate.Length(equal=3),
    )

    notes = fields.String(allow_none=True, required=False)

    @validates_schema
    def validate_freight_quote(self, data, **kwargs):
        quote_status = data.get("quote_status")
        responsibility = data.get("international_freight_responsibility")

        if quote_status == "approved" and responsibility == "not_applicable":
            raise ValidationError(
                {
                    "international_freight_responsibility": [
                        "When quote_status is approved, international_freight_responsibility cannot be not_applicable."
                    ]
                }
            )

        if data.get("quoted_amount") is not None and not data.get("quoted_currency"):
            raise ValidationError(
                {
                    "quoted_currency": [
                        "quoted_currency is required when quoted_amount is provided."
                    ]
                }
            )
        
class ImportProcessServiceCreateSchema(Schema):
    service_type = fields.String(
        required=True,
        validate=validate.OneOf(IMPORT_PROCESS_SERVICE_TYPES),
    )

    status = fields.String(
        load_default="pending",
        validate=validate.OneOf(IMPORT_PROCESS_SERVICE_STATUSES),
    )

    started_at = fields.DateTime(allow_none=True, required=False)
    completed_at = fields.DateTime(allow_none=True, required=False)
    cancelled_at = fields.DateTime(allow_none=True, required=False)

    notes = fields.String(allow_none=True, required=False)


class ImportProcessTaskCreateSchema(Schema):
    service_type = fields.String(
        required=True,
        validate=validate.OneOf(IMPORT_PROCESS_SERVICE_TYPES),
    )

    name = fields.String(
        required=True,
        validate=validate.Length(min=1, max=255),
    )

    description = fields.String(allow_none=True, required=False)

    status = fields.String(
        load_default="pending",
        validate=validate.OneOf(IMPORT_PROCESS_TASK_STATUSES),
    )

    position = fields.Integer(
        load_default=0,
        validate=validate.Range(min=0),
    )

    due_date = fields.Date(allow_none=True, required=False)

    started_at = fields.DateTime(allow_none=True, required=False)
    completed_at = fields.DateTime(allow_none=True, required=False)
    blocked_at = fields.DateTime(allow_none=True, required=False)

    blocking_reason = fields.String(allow_none=True, required=False)

    assigned_to_user_id = fields.Integer(allow_none=True, required=False)

    @validates_schema
    def validate_task_status(self, data, **kwargs):
        status = data.get("status")

        if status == "blocked" and not data.get("blocking_reason"):
            raise ValidationError(
                {
                    "blocking_reason": [
                        "blocking_reason is required when task status is blocked."
                    ]
                }
            )
        
class ImportProcessTagCreateSchema(Schema):
    tag_type = fields.String(
        required=True,
        validate=validate.OneOf(IMPORT_PROCESS_TAG_TYPES),
    )

class ImportProcessCreateSchema(Schema):
    process_number = fields.String(
        required=True,
        validate=validate.Length(min=1, max=100),
    )

    internal_reference = fields.String(
        allow_none=True,
        required=False,
        validate=validate.Length(max=100),
    )

    client_reference = fields.String(
        allow_none=True,
        required=False,
        validate=validate.Length(max=100),
    )

    client_id = fields.Integer(required=True)

    opened_at = fields.Date(required=True)

    current_stage = fields.String(
        load_default="pre_shipment",
        validate=validate.OneOf(IMPORT_PROCESS_STAGES),
    )

    notes = fields.String(allow_none=True, required=False)

    shipment = fields.Nested(
        ImportProcessShipmentCreateSchema,
        required=False,
        allow_none=True,
    )

    freight = fields.Nested(
        ImportProcessFreightCreateSchema,
        required=False,
        allow_none=True,
    )

    services = fields.List(
        fields.Nested(ImportProcessServiceCreateSchema),
        required=False,
        load_default=list,
    )

    tags = fields.List(
        fields.Nested(ImportProcessTagCreateSchema),
        required=False,
        load_default=list,
    )

    @validates_schema
    def validate_unique_services_and_tags(self, data, **kwargs):
        services = data.get("services") or []
        tags = data.get("tags") or []

        service_types = [service["service_type"] for service in services]
        tag_types = [tag["tag_type"] for tag in tags]

        if len(service_types) != len(set(service_types)):
            raise ValidationError(
                {
                    "services": [
                        "Duplicated service_type is not allowed for the same import process."
                    ]
                }
            )

        if len(tag_types) != len(set(tag_types)):
            raise ValidationError(
                {
                    "tags": [
                        "Duplicated tag_type is not allowed for the same import process."
                    ]
                }
            )
        
class ImportProcessUpdateSchema(Schema):
    process_number = fields.String(
        required=False,
        validate=validate.Length(min=1, max=100),
    )

    internal_reference = fields.String(
        allow_none=True,
        required=False,
        validate=validate.Length(max=100),
    )

    client_reference = fields.String(
        allow_none=True,
        required=False,
        validate=validate.Length(max=100),
    )

    client_id = fields.Integer(required=False)

    opened_at = fields.Date(required=False)

    current_stage = fields.String(
        required=False,
        validate=validate.OneOf(IMPORT_PROCESS_STAGES),
    )

    notes = fields.String(allow_none=True, required=False)

class ImportProcessShipmentUpdateSchema(Schema):
    estimated_departure_at = fields.Date(allow_none=True, required=False)
    estimated_arrival_at = fields.Date(allow_none=True, required=False)

    actual_departure_at = fields.Date(allow_none=True, required=False)
    actual_arrival_at = fields.Date(allow_none=True, required=False)

    origin = fields.String(allow_none=True, required=False)
    destination = fields.String(allow_none=True, required=False)

    vessel_name = fields.String(allow_none=True, required=False)
    voyage_number = fields.String(allow_none=True, required=False)

    master_bl = fields.String(allow_none=True, required=False)
    house_bl = fields.String(allow_none=True, required=False)

    container_number = fields.String(allow_none=True, required=False)

    notes = fields.String(allow_none=True, required=False)

class ImportProcessFreightUpdateSchema(Schema):
    international_freight_responsibility = fields.String(
        required=False,
        validate=validate.OneOf(INTERNATIONAL_FREIGHT_RESPONSIBILITIES),
    )

    quote_status = fields.String(
        required=False,
        validate=validate.OneOf(FREIGHT_QUOTE_STATUSES),
    )

    quote_requested_at = fields.DateTime(allow_none=True, required=False)
    quote_approved_at = fields.DateTime(allow_none=True, required=False)
    quote_rejected_at = fields.DateTime(allow_none=True, required=False)

    provider_name = fields.String(allow_none=True, required=False)

    quoted_amount = fields.Decimal(
        as_string=True,
        places=2,
        allow_none=True,
        required=False,
    )

    quoted_currency = fields.String(
        allow_none=True,
        required=False,
        validate=validate.Length(equal=3),
    )

    notes = fields.String(allow_none=True, required=False)

class ImportProcessServiceUpdateSchema(Schema):
    service_type = fields.String(
        required=False,
        validate=validate.OneOf(IMPORT_PROCESS_SERVICE_TYPES),
    )

    responsibility = fields.String(
        required=False,
        validate=validate.OneOf(IMPORT_PROCESS_SERVICE_RESPONSIBILITIES),
    )

    responsible_name = fields.String(
        allow_none=True,
        required=False,
        validate=validate.Length(max=255),
    )

    status = fields.String(
        required=False,
        validate=validate.OneOf(IMPORT_PROCESS_SERVICE_STATUSES),
    )

    started_at = fields.DateTime(allow_none=True, required=False)
    completed_at = fields.DateTime(allow_none=True, required=False)
    cancelled_at = fields.DateTime(allow_none=True, required=False)

    notes = fields.String(allow_none=True, required=False)

class ImportProcessTaskUpdateSchema(Schema):
    service_type = fields.String(
        required=False,
        validate=validate.OneOf(IMPORT_PROCESS_SERVICE_TYPES),
    )

    name = fields.String(
        required=False,
        validate=validate.Length(min=1, max=255),
    )

    description = fields.String(allow_none=True, required=False)

    status = fields.String(
        required=False,
        validate=validate.OneOf(IMPORT_PROCESS_TASK_STATUSES),
    )

    position = fields.Integer(
        required=False,
        validate=validate.Range(min=0),
    )

    due_date = fields.Date(allow_none=True, required=False)

    started_at = fields.DateTime(allow_none=True, required=False)
    completed_at = fields.DateTime(allow_none=True, required=False)
    blocked_at = fields.DateTime(allow_none=True, required=False)

    blocking_reason = fields.String(allow_none=True, required=False)

    assigned_to_user_id = fields.Integer(allow_none=True, required=False)

    @validates_schema
    def validate_task_status(self, data, **kwargs):
        status = data.get("status")

        if status == "blocked" and data.get("blocking_reason") in (None, ""):
            raise ValidationError(
                {
                    "blocking_reason": [
                        "blocking_reason is required when task status is blocked."
                    ]
                }
            )

class ImportProcessTagUpdateSchema(Schema):
    tag_type = fields.String(
        required=True,
        validate=validate.OneOf(IMPORT_PROCESS_TAG_TYPES),
    )

class ImportProcessStageUpdateSchema(Schema):
    current_stage = fields.String(
        required=True,
        validate=validate.OneOf(IMPORT_PROCESS_STAGES),
    )

class ImportProcessTaskStatusUpdateSchema(Schema):
    status = fields.String(
        required=True,
        validate=validate.OneOf(IMPORT_PROCESS_TASK_STATUSES),
    )

    blocking_reason = fields.String(allow_none=True, required=False)

    @validates_schema
    def validate_blocking_reason(self, data, **kwargs):
        if data.get("status") == "blocked" and not data.get("blocking_reason"):
            raise ValidationError(
                {
                    "blocking_reason": [
                        "blocking_reason is required when status is blocked."
                    ]
                }
            )
        
class ImportProcessTaskReorderItemSchema(Schema):
    id = fields.Integer(required=True)
    position = fields.Integer(
        required=True,
        validate=validate.Range(min=0),
    )


class ImportProcessTaskReorderSchema(Schema):
    tasks = fields.List(
        fields.Nested(ImportProcessTaskReorderItemSchema),
        required=True,
        validate=validate.Length(min=1),
    )

class ImportProcessFreightQuoteUpdateSchema(Schema):
    international_freight_responsibility = fields.String(
        required=True,
        validate=validate.OneOf(INTERNATIONAL_FREIGHT_RESPONSIBILITIES),
    )

    quote_status = fields.String(
        required=True,
        validate=validate.OneOf(FREIGHT_QUOTE_STATUSES),
    )

    provider_name = fields.String(allow_none=True, required=False)

    quoted_amount = fields.Decimal(
        as_string=True,
        places=2,
        allow_none=True,
        required=False,
    )

    quoted_currency = fields.String(
        allow_none=True,
        required=False,
        validate=validate.Length(equal=3),
    )

    notes = fields.String(allow_none=True, required=False)

    @validates_schema
    def validate_quote(self, data, **kwargs):
        quote_status = data.get("quote_status")
        responsibility = data.get("international_freight_responsibility")

        if quote_status == "approved" and responsibility == "not_applicable":
            raise ValidationError(
                {
                    "international_freight_responsibility": [
                        "When quote_status is approved, responsibility cannot be not_applicable."
                    ]
                }
            )

        if data.get("quoted_amount") is not None and not data.get("quoted_currency"):
            raise ValidationError(
                {
                    "quoted_currency": [
                        "quoted_currency is required when quoted_amount is provided."
                    ]
                }
            )
        
class ImportProcessClientOutputSchema(Schema):
    id = fields.String()
    name = fields.String()
    taxId = fields.String(allow_none=True)


class ImportProcessDatesOutputSchema(Schema):
    openedAt = fields.Date(allow_none=True)

    estimatedDepartureAt = fields.Date(allow_none=True)
    estimatedArrivalAt = fields.Date(allow_none=True)

    actualDepartureAt = fields.Date(allow_none=True)
    actualArrivalAt = fields.Date(allow_none=True)


class ImportProcessShipmentOutputSchema(Schema):
    id = fields.String()

    origin = fields.String(allow_none=True)
    destination = fields.String(allow_none=True)

    estimatedDepartureAt = fields.Date(allow_none=True)
    estimatedArrivalAt = fields.Date(allow_none=True)

    actualDepartureAt = fields.Date(allow_none=True)
    actualArrivalAt = fields.Date(allow_none=True)

    vesselName = fields.String(allow_none=True)
    voyageNumber = fields.String(allow_none=True)

    masterBl = fields.String(allow_none=True)
    houseBl = fields.String(allow_none=True)

    containerNumber = fields.String(allow_none=True)

    notes = fields.String(allow_none=True)


class ImportProcessFreightOutputSchema(Schema):
    id = fields.String()

    internationalFreightResponsibility = fields.String(
        validate=validate.OneOf(INTERNATIONAL_FREIGHT_RESPONSIBILITIES)
    )

    quoteStatus = fields.String(
        validate=validate.OneOf(FREIGHT_QUOTE_STATUSES)
    )

    quoteRequestedAt = fields.DateTime(allow_none=True)
    quoteApprovedAt = fields.DateTime(allow_none=True)
    quoteRejectedAt = fields.DateTime(allow_none=True)

    providerName = fields.String(allow_none=True)

    quotedAmount = fields.Decimal(as_string=True, allow_none=True)
    quotedCurrency = fields.String(allow_none=True)

    notes = fields.String(allow_none=True)


class ImportProcessServiceOutputSchema(Schema):
    id = fields.String()

    type = fields.String(
        validate=validate.OneOf(IMPORT_PROCESS_SERVICE_TYPES)
    )

    status = fields.String(
        validate=validate.OneOf(IMPORT_PROCESS_SERVICE_STATUSES)
    )

    startedAt = fields.DateTime(allow_none=True)
    completedAt = fields.DateTime(allow_none=True)
    cancelledAt = fields.DateTime(allow_none=True)

    notes = fields.String(allow_none=True)


class ImportProcessTaskOutputSchema(Schema):
    id = fields.String()

    name = fields.String()
    description = fields.String(allow_none=True)

    status = fields.String(
        validate=validate.OneOf(IMPORT_PROCESS_TASK_STATUSES)
    )

    serviceType = fields.String(
        validate=validate.OneOf(IMPORT_PROCESS_SERVICE_TYPES)
    )

    position = fields.Integer()

    dueDate = fields.Date(allow_none=True)

    startedAt = fields.DateTime(allow_none=True)
    completedAt = fields.DateTime(allow_none=True)
    blockedAt = fields.DateTime(allow_none=True)

    blockingReason = fields.String(allow_none=True)

    assignedToUserId = fields.String(allow_none=True)


class ImportProcessOutputSchema(Schema):
    id = fields.String()

    processNumber = fields.String()
    internalReference = fields.String(allow_none=True)
    clientReference = fields.String(allow_none=True)

    client = fields.Nested(ImportProcessClientOutputSchema)

    dates = fields.Nested(ImportProcessDatesOutputSchema)

    shipment = fields.Nested(
        ImportProcessShipmentOutputSchema,
        allow_none=True,
    )

    freight = fields.Nested(
        ImportProcessFreightOutputSchema,
        allow_none=True,
    )

    services = fields.List(
        fields.Nested(ImportProcessServiceOutputSchema)
    )

    currentStage = fields.String(
        validate=validate.OneOf(IMPORT_PROCESS_STAGES)
    )

    tags = fields.List(
        fields.String(validate=validate.OneOf(IMPORT_PROCESS_TAG_TYPES))
    )

    tasks = fields.List(
        fields.Nested(ImportProcessTaskOutputSchema)
    )

    createdAt = fields.DateTime(allow_none=True)
    updatedAt = fields.DateTime(allow_none=True)

class ImportProcessShipmentCreateSchema(Schema):
    estimated_departure_at = fields.Date(required=False, allow_none=True)
    estimated_arrival_at = fields.Date(required=False, allow_none=True)

    actual_departure_at = fields.Date(required=False, allow_none=True)
    actual_arrival_at = fields.Date(required=False, allow_none=True)

    origin = fields.String(required=False, allow_none=True)
    destination = fields.String(required=False, allow_none=True)

    vessel_name = fields.String(required=False, allow_none=True)
    voyage_number = fields.String(required=False, allow_none=True)

    master_bl = fields.String(required=False, allow_none=True)
    house_bl = fields.String(required=False, allow_none=True)

    container_number = fields.String(required=False, allow_none=True)

    notes = fields.String(required=False, allow_none=True)


class ImportProcessFreightCreateSchema(Schema):
    international_freight_responsibility = fields.String(
        required=True,
        validate=validate.OneOf(INTERNATIONAL_FREIGHT_RESPONSIBILITIES),
    )

    quote_status = fields.String(
        required=True,
        validate=validate.OneOf(FREIGHT_QUOTE_STATUSES),
    )

    provider_name = fields.String(required=False, allow_none=True)

    quoted_amount = fields.Decimal(
        required=False,
        allow_none=True,
        as_string=True,
        places=2,
    )

    quoted_currency = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(equal=3),
    )

    quote_requested_at = fields.DateTime(required=False, allow_none=True)
    quote_approved_at = fields.DateTime(required=False, allow_none=True)
    quote_rejected_at = fields.DateTime(required=False, allow_none=True)

    notes = fields.String(required=False, allow_none=True)

    @validates_schema
    def validate_freight(self, data, **kwargs):
        quote_status = data.get("quote_status")
        responsibility = data.get("international_freight_responsibility")

        if quote_status == "approved" and responsibility == "not_applicable":
            raise ValidationError(
                {
                    "international_freight_responsibility": [
                        "Quando quote_status for approved, international_freight_responsibility não pode ser not_applicable."
                    ]
                }
            )

        if data.get("quoted_amount") is not None and not data.get("quoted_currency"):
            raise ValidationError(
                {
                    "quoted_currency": [
                        "quoted_currency é obrigatório quando quoted_amount for informado."
                    ]
                }
            )


class ImportProcessServiceCreateSchema(Schema):
    service_type = fields.String(
        required=True,
        validate=validate.OneOf(IMPORT_PROCESS_SERVICE_TYPES),
    )

    responsibility = fields.String(
        load_default="internal",
        validate=validate.OneOf(IMPORT_PROCESS_SERVICE_RESPONSIBILITIES),
    )

    responsible_name = fields.String(
        allow_none=True,
        required=False,
        validate=validate.Length(max=255),
    )

    status = fields.String(
        load_default="pending",
        validate=validate.OneOf(IMPORT_PROCESS_SERVICE_STATUSES),
    )

    started_at = fields.DateTime(allow_none=True, required=False)
    completed_at = fields.DateTime(allow_none=True, required=False)
    cancelled_at = fields.DateTime(allow_none=True, required=False)

    notes = fields.String(allow_none=True, required=False)

    @validates_schema
    def validate_responsible_name(self, data, **kwargs):
        responsibility = data.get("responsibility")

        if responsibility == "third_party" and not data.get("responsible_name"):
            raise ValidationError(
                {
                    "responsible_name": [
                        "responsible_name is required when responsibility is third_party."
                    ]
                }
            )

class ImportProcessTagCreateSchema(Schema):
    tag_type = fields.String(
        required=True,
        validate=validate.OneOf(IMPORT_PROCESS_TAG_TYPES),
    )


class ImportProcessCreateSchema(Schema):
    process_number = fields.String(
        required=True,
        validate=validate.Length(min=1, max=100),
    )

    internal_reference = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(max=100),
    )

    client_reference = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(max=100),
    )

    client_id = fields.UUID(required=True)

    opened_at = fields.DateTime(required=True)

    current_stage = fields.String(
        required=True,
        validate=validate.OneOf(IMPORT_PROCESS_STAGES),
    )

    metadata_json = fields.Dict(required=False, allow_none=True)

    notes = fields.String(required=False, allow_none=True)

    shipment = fields.Nested(
        ImportProcessShipmentCreateSchema,
        required=False,
        allow_none=True,
    )

    freight = fields.Nested(
        ImportProcessFreightCreateSchema,
        required=False,
        allow_none=True,
    )

    services = fields.List(
        fields.Nested(ImportProcessServiceCreateSchema),
        required=False,
        load_default=list,
    )

    tags = fields.List(
        fields.Nested(ImportProcessTagCreateSchema),
        required=False,
        load_default=list,
    )

    @validates_schema
    def validate_unique_items(self, data, **kwargs):
        services = data.get("services") or []
        tags = data.get("tags") or []

        service_types = [item["service_type"] for item in services]
        tag_types = [item["tag_type"] for item in tags]

        if len(service_types) != len(set(service_types)):
            raise ValidationError(
                {
                    "services": [
                        "Não é permitido enviar serviços duplicados para o mesmo processo."
                    ]
                }
            )

        if len(tag_types) != len(set(tag_types)):
            raise ValidationError(
                {
                    "tags": [
                        "Não é permitido enviar tags duplicadas para o mesmo processo."
                    ]
                }
            )