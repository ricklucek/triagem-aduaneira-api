from marshmallow import Schema, fields

from app.models.enums import AssignmentRole, ScopeStatus
from app.schemas.common import EnumField, UUIDStringField
from app.schemas.clients import ClientSummarySchema, ClientSchema, ClientContactSchema
from app.schemas.identity import UserSummarySchema
from .operations import ScopeOperationsSchema
from .taxes import ScopeTaxesSchema
from .services import ScopeServicesSchema
from .financial import ScopeFinancialSchema, ScopeGeneralSchema


class ScopeAssignmentsSchema(Schema):
    commercialResponsible = fields.Method("get_commercial_responsible")
    importDaAnalysts = fields.Method("get_import_da_analysts")
    importAeAnalysts = fields.Method("get_import_ae_analysts")
    exportDaAnalysts = fields.Method("get_export_da_analysts")
    exportAeAnalysts = fields.Method("get_export_ae_analysts")

    user_schema = UserSummarySchema()

    def _users_for_role(self, scope, role: AssignmentRole):
        return [
            self.user_schema.dump(assignment.user)
            for assignment in scope.assignments_by_role(role)
            if assignment.user
        ]

    def get_commercial_responsible(self, scope):
        if scope.commercial_responsible_user:
            return self.user_schema.dump(scope.commercial_responsible_user)

        users = self._users_for_role(scope, AssignmentRole.COMMERCIAL_RESPONSIBLE)
        return users[0] if users else None

    def get_import_da_analysts(self, scope):
        return self._users_for_role(scope, AssignmentRole.IMPORT_DA_ANALYST)

    def get_import_ae_analysts(self, scope):
        return self._users_for_role(scope, AssignmentRole.IMPORT_AE_ANALYST)

    def get_export_da_analysts(self, scope):
        return self._users_for_role(scope, AssignmentRole.EXPORT_DA_ANALYST)

    def get_export_ae_analysts(self, scope):
        return self._users_for_role(scope, AssignmentRole.EXPORT_AE_ANALYST)


class ScopeStructuredSchema(Schema):
    id = UUIDStringField(dump_only=True)
    status = EnumField(ScopeStatus)
    version = fields.Integer()
    createdAt = fields.DateTime(attribute="created_at", allow_none=True)
    updatedAt = fields.DateTime(attribute="updated_at", allow_none=True)
    lastPublishedAt = fields.DateTime(attribute="last_published_at", allow_none=True)
    company = fields.Nested(ClientSchema, attribute="client", allow_none=True)
    contacts = fields.Method("get_contacts")
    assignments = fields.Method("get_assignments")
    operations = fields.Method("get_operations")
    taxes = fields.Method("get_taxes")
    services = fields.Method("get_services")
    financial = fields.Method("get_financial")
    general = fields.Method("get_general")
    contact_schema = ClientContactSchema(many=True)
    assignments_schema = ScopeAssignmentsSchema()
    operations_schema = ScopeOperationsSchema()
    taxes_schema = ScopeTaxesSchema()
    services_schema = ScopeServicesSchema()
    financial_schema = ScopeFinancialSchema()
    general_schema = ScopeGeneralSchema()

    def get_contacts(self, obj):
        if not obj.client:
            return []

        return self.contact_schema.dump([contact for contact in obj.client.contacts if contact.active])

    def get_assignments(self, obj):
        return self.assignments_schema.dump(obj)

    def get_operations(self, obj):
        return self.operations_schema.dump(obj)

    def get_taxes(self, obj):
        return self.taxes_schema.dump(obj)

    def get_services(self, obj):
        return self.services_schema.dump(obj)

    def get_financial(self, obj):
        if not obj.financial_profile:
            return {
                "paymentPreference": None,
                "refundPixKey": None,
                "notes": None,
                "refundBankAccounts": [],
            }

        return self.financial_schema.dump(obj.financial_profile)

    def get_general(self, obj):
        if not obj.general_profile:
            return {"description": None}

        return self.general_schema.dump(obj.general_profile)


class ScopeSummarySchema(Schema):
    id = UUIDStringField()
    status = EnumField(ScopeStatus)
    version = fields.Integer(allow_none=True)
    updatedAt = fields.DateTime(attribute="updated_at", allow_none=True)
    lastPublishedAt = fields.DateTime(attribute="last_published_at", allow_none=True)
    company = fields.Nested(ClientSummarySchema, attribute="client", allow_none=True)
    commercialResponsible = fields.Nested(
        UserSummarySchema,
        attribute="commercial_responsible_user",
        allow_none=True,
    )
