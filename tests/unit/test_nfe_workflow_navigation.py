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
