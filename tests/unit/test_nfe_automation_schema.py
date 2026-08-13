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


@pytest.mark.parametrize("cst", ["40", "41", "50"])
def test_accepts_non_taxed_icms_rule_without_nominal_rate(cst):
    payload = {
        "name": "PR exoneração integral diagnóstico",
        "issuer_state": "PR",
        "import_purpose": "resale",
        "configuration_json": {
            "icms_origin": "1",
            "icms_cst": cst,
            "icms_tax_treatment_confirmed": False,
        },
    }

    result = ClientImportTaxRuleSchema().load(payload)

    assert result["configuration_json"]["icms_cst"] == cst
    assert "icms_rate" not in result["configuration_json"]


def test_rejects_nominal_rate_for_non_taxed_icms_rule():
    payload = {
        "name": "PR exoneração inválida",
        "issuer_state": "PR",
        "import_purpose": "resale",
        "configuration_json": {
            "icms_cst": "40",
            "icms_rate": "19.5",
        },
    }

    with pytest.raises(ValidationError, match="não aceita alíquota nominal"):
        ClientImportTaxRuleSchema().load(payload)
