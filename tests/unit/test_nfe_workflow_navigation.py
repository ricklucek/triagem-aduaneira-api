from datetime import date

from app.models import ClientImportTaxRule
from app.services.import_process import ImportNfeService


def test_portal_unico_configuration_belongs_to_duimp_step():
    navigation = ImportNfeService._workflow_navigation(
        "configure_provider_connection"
    )

    assert navigation["current_step"] == "duimp"
    assert navigation["furthest_available_step"] == "duimp"
    assert navigation["steps"][0] == {
        "key": "client",
        "label": "Cliente",
        "status": "completed",
        "can_view": True,
    }
    assert navigation["steps"][1] == {
        "key": "duimp",
        "label": "DUIMP",
        "status": "current",
        "can_view": True,
    }


def tax_rule(**overrides):
    values = {
        "name": "Regra padrão",
        "issuer_state": "PR",
        "import_purpose": "resale",
        "import_modality": "direct",
        "tax_regime": "3",
        "ncm_pattern": None,
        "priority": 100,
        "active": True,
    }
    values.update(overrides)
    return ClientImportTaxRule(**values)


def test_tax_rule_conflict_requires_equal_score_and_overlapping_scope():
    first = tax_rule(name="Regra A")
    same_scope = tax_rule(name="Regra B")
    higher_priority = tax_rule(name="Regra prioritária", priority=200)
    other_purpose = tax_rule(name="Uso e consumo", import_purpose="use_consumption")

    assert ImportNfeService._tax_rules_are_ambiguous(first, same_scope) is True
    assert ImportNfeService._tax_rules_are_ambiguous(first, higher_priority) is False
    assert ImportNfeService._tax_rules_are_ambiguous(first, other_purpose) is False


def test_tax_rule_conflict_respects_ncm_and_non_overlapping_validity():
    ncm_8302 = tax_rule(ncm_pattern="8302")
    ncm_4016 = tax_rule(ncm_pattern="4016")
    old_rule = tax_rule(
        effective_from=date(2025, 1, 1),
        effective_until=date(2025, 12, 31),
    )
    new_rule = tax_rule(effective_from=date(2026, 1, 1))

    assert ImportNfeService._tax_rules_are_ambiguous(ncm_8302, ncm_4016) is False
    assert ImportNfeService._tax_rules_are_ambiguous(old_rule, new_rule) is False
