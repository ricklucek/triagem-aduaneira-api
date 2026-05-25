from marshmallow import Schema, fields

from .common import EnumField, UUIDStringField
from .identity import (
    OrganizationSchema,
    UserSchema,
    UserSummarySchema,
    AdminProfileSchema,
)
from .clients import (
    ClientSchema,
    ClientContactSchema,
    ClientSummarySchema,
    ClientPayloadSchema,
    ClientContactPayloadSchema,
    ClientListQuerySchema,
    ClientUpdateSchema
)
from .prepostos import (
    PrepostoSchema,
    PrepostoContactSchema,
    PrepostoLocationSchema,
    ScopePrepostoSchema,
    PrepostoPayloadSchema,
    PrepostoContactPayloadSchema,
    PrepostoLocationPayloadSchema,
)
from .scopes.response import ScopeStructuredSchema, ScopeSummarySchema
from .scopes.payload import ScopeCreatePayloadSchema, ScopeUpdatePayloadSchema
from .scopes.bulk import (
    ScopeBulkAssignmentSummaryQuerySchema,
    ScopeBulkAssignmentScopesQuerySchema,
    ScopeBulkAssignmentUpdatePayloadSchema,
)