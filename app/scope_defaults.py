from copy import deepcopy
from datetime import datetime, timezone


_DEFAULT_CASCO_BANK = {
    "bank": None,
    "agency": None,
    "account": None,
    "pixKey": None,
}


DEFAULT_SCOPE_DRAFT = {
    "globalsSnapshot": {
        "salaryMinimumBRL": 1518,
        "cascoBank": deepcopy(_DEFAULT_CASCO_BANK),
    },
    "client": {
        "cnpj": None,
        "razaoSocial": None,
        "nomeFantasia": None,
        "ie": None,
        "im": None,
        "regimeTributario": None,
        "radarModalidade": None,
        "enderecoEscritorio": None,
        "enderecoArmazem": None,
        "responsavelComercialId": None,
    },
    "contacts": [],
    "operation": {
        "types": [],
    },
    "importSection": {
        "modal": None,
        "entryLocations": [],
        "releaseWarehouses": [],
        "ncm": [],
        "cnaePrincipal": None,
        "cnaeSecundario": [],
        "liLpco": {
            "enabled": False,
            "anuencias": [],
        },
    },
    "exportSection": {
        "modal": None,
        "departureLocations": [],
        "ncm": [],
        "cnaeSecundario": [],
    },
    "services": [],
    "meta": {
        "status": "draft",
        "version": 1,
        "source": "MANUAL",
        "updatedAt": "",
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_default_scope_draft() -> dict:
    draft = deepcopy(DEFAULT_SCOPE_DRAFT)
    if not draft["meta"]["updatedAt"]:
        draft["meta"]["updatedAt"] = _now_iso()
    return draft


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


def normalize_scope_draft(draft: dict | None) -> dict:
    normalized = merge_scope_draft(build_default_scope_draft(), draft or {})

    # Garantias mínimas para listas/objetos esperados pelo backend
    if not isinstance(normalized.get("contacts"), list):
        normalized["contacts"] = []

    if not isinstance(normalized.get("services"), list):
        normalized["services"] = []

    if not isinstance(normalized.get("operation"), dict):
        normalized["operation"] = {"types": []}

    if not isinstance(normalized["operation"].get("types"), list):
        normalized["operation"]["types"] = []

    if not isinstance(normalized.get("importSection"), dict):
        normalized["importSection"] = deepcopy(DEFAULT_SCOPE_DRAFT["importSection"])

    if not isinstance(normalized.get("exportSection"), dict):
        normalized["exportSection"] = deepcopy(DEFAULT_SCOPE_DRAFT["exportSection"])

    if not isinstance(normalized.get("globalsSnapshot"), dict):
        normalized["globalsSnapshot"] = deepcopy(DEFAULT_SCOPE_DRAFT["globalsSnapshot"])

    if not isinstance(normalized.get("client"), dict):
        normalized["client"] = deepcopy(DEFAULT_SCOPE_DRAFT["client"])

    if not isinstance(normalized.get("meta"), dict):
        normalized["meta"] = deepcopy(DEFAULT_SCOPE_DRAFT["meta"])

    if not normalized["meta"].get("updatedAt"):
        normalized["meta"]["updatedAt"] = _now_iso()

    return normalized


def apply_admin_defaults(draft: dict, admin_settings: dict | None) -> dict:
    normalized = normalize_scope_draft(draft)

    if not admin_settings:
        return normalized

    normalized["globalsSnapshot"] = merge_scope_draft(
        deepcopy(DEFAULT_SCOPE_DRAFT["globalsSnapshot"]),
        {
            "salaryMinimumBRL": admin_settings.get("salaryMinimumBRL", 1518),
            "cascoBank": admin_settings.get("cascoBank", {}),
        },
    )

    return normalized