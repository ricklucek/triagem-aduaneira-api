import pytest
from marshmallow import ValidationError

from app.schemas.nfe_automation import ClientImportTaxRuleSchema


def diagnostic_icms51_rule():
    return {
        "name": "SC industrializacao diferimento integral",
        "issuer_state": "SC",
        "import_purpose": "industrialization",
        "configuration_json": {
            "icms_origin": "1",
            "icms_cst": "51",
            "icms_deferment_rate": "100",
        },
    }


def test_accepts_diagnostic_icms51_without_nominal_rate():
    result = ClientImportTaxRuleSchema().load(diagnostic_icms51_rule())

    assert result["configuration_json"]["icms_cst"] == "51"
    assert "icms_rate" not in result["configuration_json"]


def test_rejects_partial_deferment_without_nominal_rate():
    payload = diagnostic_icms51_rule()
    payload["configuration_json"]["icms_deferment_rate"] = "50"

    with pytest.raises(ValidationError, match="diferimento de 100%"):
        ClientImportTaxRuleSchema().load(payload)
