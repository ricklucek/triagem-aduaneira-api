from sqlalchemy.orm import joinedload, selectinload

from app.models import (
    Client,
    Scope,
    ScopeAssignment,
    ScopeFinancialProfile,
    ScopeOperationDetail,
    ScopePreposto,
    ScopeService,
)


def scope_structured_options():
    """Relationship loading options for ScopeStructuredSchema.

    Use this in detail endpoints to avoid N+1 queries while the schema composes
    the response from relational models.
    """
    return (
        joinedload(Scope.client).selectinload(Client.contacts),
        joinedload(Scope.commercial_responsible_user),
        selectinload(Scope.assignments).joinedload(ScopeAssignment.user),
        joinedload(Scope.operation_profile),
        selectinload(Scope.operation_details).selectinload(ScopeOperationDetail.ncms),
        selectinload(Scope.operation_details).selectinload(ScopeOperationDetail.locations),
        selectinload(Scope.operation_details).selectinload(ScopeOperationDetail.authorities),
        selectinload(Scope.operation_details).selectinload(ScopeOperationDetail.destination_purposes),
        joinedload(ScopeOperationDetail.federal_tax_profile),
        joinedload(ScopeOperationDetail.afrmm_profile),
        joinedload(ScopeOperationDetail.icms_profile),
        selectinload(Scope.services).joinedload(ScopeService.service_catalog),
        selectinload(Scope.services).joinedload(ScopeService.responsible_user),
        selectinload(Scope.services).joinedload(ScopeService.freight_detail),
        selectinload(Scope.services).joinedload(ScopeService.insurance_detail),
        selectinload(Scope.services).joinedload(ScopeService.customs_broker_detail),
        selectinload(Scope.services).joinedload(ScopeService.certificate_detail),
        selectinload(Scope.prepostos).joinedload(ScopePreposto.preposto),
        selectinload(Scope.prepostos).selectinload(ScopePreposto.cities),
        joinedload(Scope.financial_profile).selectinload(ScopeFinancialProfile.refund_bank_accounts),
        joinedload(Scope.general_profile),
    )
