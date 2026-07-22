from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services.nfe_access_key_service import NfeAccessKeyService


def draft(**overrides):
    values = {
        "number": 14422,
        "series": "1",
        "model": "55",
        "fiscal_payload": {
            "issuer": {
                "cnpj": "00000000000191",
                "address": {"state": "PR"},
            }
        },
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_generates_deterministic_44_digit_access_key():
    result = NfeAccessKeyService().generate_for_draft(
        draft=draft(),
        issue_datetime=datetime(2026, 7, 16, 11, 18, 38),
        tp_emis="1",
        c_nf="76336237",
    )

    assert result["access_key"] == "41260700000000000191550010000144221763362374"
    assert len(result["access_key"]) == 44
    assert result["cUF"] == "41"
    assert result["AAMM"] == "2607"
    assert result["series"] == "001"
    assert result["number"] == "000014422"


def test_rejects_unmapped_issuer_state():
    invalid = draft()
    invalid.fiscal_payload["issuer"]["address"]["state"] = "EX"

    with pytest.raises(ValueError, match="UF inválida"):
        NfeAccessKeyService().generate_for_draft(draft=invalid)
