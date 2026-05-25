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

class OrganizationFixedInfoSchema(Schema):
    salarioMinimoVigente = fields.Decimal(as_string=False, required=True)
    dadosBancariosCasco = fields.Dict(required=True)
    
class PrepostoCreateSchema(Schema):
    pass

class PrepostoUpdateSchema(Schema):
    pass

class PrepostoContatoSchema(Schema):
    pass

class PrepostoContatoCreateSchema(Schema):
    pass

class PrepostoContatoUpdateSchema(Schema):
    pass

class PrepostoLocalidadeSchema(Schema):
    pass

class PrepostoLocalidadeCreateSchema(Schema):
    pass

class PrepostoLocalidadeUpdateSchema(Schema):
    pass

class PrepostoLookupResponseSchema(Schema):
    pass

class ScopeBulkResponsibleSchema(Schema):
    pass

class ScopeListQuerySchema(Schema):
    pass

class ScopeSchema(Schema):
    pass
