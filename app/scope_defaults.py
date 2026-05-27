from copy import deepcopy
from copy import deepcopy

_DEFAULT_BANK_ACCOUNT = {"banco": "", "agencia": "", "conta": ""}

DEFAULT_SCOPE_DRAFT = {
    "company": {
        "taxId": "",
        "legalName": "",
        "tradeName": None,
        "stateRegistration": None,
        "municipalRegistration": None,
        "officeAddress": None,
        "warehouseAddress": None,
        "mainCnae": None,
        "secondaryCnae": None,
        "taxRegime": None,
        "radarMode": None,
    },
    "contacts": [],
    "assignments": {
        "commercialResponsibleId": None,
        "importDaAnalystIds": [],
        "importAeAnalystIds": [],
        "exportDaAnalystIds": [],
        "exportAeAnalystIds": [],
    },
    "operations": {
        "types": [],
        "importOperation": None,
        "exportOperation": None,
    },
    "taxes": {
        "importTaxes": None,
        "exportTaxes": None,
    },
    "services": {
        "items": [],
        "prepostos": [],
    },
    "financial": {
        "paymentPreference": None,
        "refundPixKey": None,
        "refundBankAccounts": [],
        "notes": None,
    },
    "general": {
        "description": None,
    },
}

def build_default_scope_draft() -> dict:
    return deepcopy(DEFAULT_SCOPE_DRAFT)


def merge_scope_draft(base: dict, patch: dict) -> dict:
    if not isinstance(base, dict):
        return deepcopy(patch)

    result = deepcopy(base)
    if not isinstance(patch, dict):
        return result

    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_scope_draft(result[key], value)
        else:
            result[key] = value
    return result


def apply_admin_defaults(draft: dict, admin_settings: dict | None) -> dict:
    normalized = merge_scope_draft(build_default_scope_draft(), draft)
    if not admin_settings:
        return normalized

    normalized["informacoesFixas"] = {
        "salarioMinimoVigente": admin_settings.get("salarioMinimoVigente", 0),
        "dadosBancariosCasco": merge_scope_draft(
            deepcopy(_DEFAULT_BANK_ACCOUNT),
            admin_settings.get("dadosBancariosCasco", {}),
        ),
    }
    return normalized