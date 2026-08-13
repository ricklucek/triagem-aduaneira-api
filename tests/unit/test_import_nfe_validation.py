from types import SimpleNamespace

from app.services.import_process import ImportNfeService


def test_validation_rejects_item_not_enriched_by_catalog():
    service = ImportNfeService(
        current_user=SimpleNamespace(organization_id=None, id=None)
    )

    result = service.validate_nfe_payload(
        {
            "document": {
                "model": "55",
                "operation_type": "entry",
                "environment": "homologation",
                "series": "1",
            },
            "duimp": {
                "number": "26BR0000000000-1",
                "registration_date": "2026-07-14",
                "clearance_location": "PARANAGUA",
                "clearance_state": "PR",
                "clearance_date": "2026-07-15",
                "transport_mode_code": "1",
            },
            "items": [
                {
                    "description": "Mercadoria importada",
                    "ncm": "87087090",
                    "cfop": "3102",
                    "commercial_quantity": "1",
                    "product_value": "100",
                    "import_payload": {"duimp_item_number": "1"},
                    "tax_payload": {
                        tax: {"value": "1"}
                        for tax in ("icms", "ipi", "ii", "pis", "cofins")
                    },
                }
            ],
        }
    )

    assert {
        "field": "items[1].description",
        "message": "Produto não enriquecido pelo Catálogo de Produtos.",
    } in result.errors


def test_validation_warns_and_blocks_diagnostic_icms_authorization():
    service = ImportNfeService(
        current_user=SimpleNamespace(organization_id=None, id=None)
    )
    authorization = service._authorization_metadata(
        [
            {
                "tax_payload": {
                    "icms": {
                        "cst": "51",
                        "diagnostic_only": True,
                    }
                }
            }
        ]
    )

    assert authorization["ready"] is False
    assert authorization["mode"] == "diagnostic"
    assert authorization["blockers"][0]["code"] == (
        "missing_nominal_icms_rate"
    )


def test_validation_blocks_unconfirmed_non_taxed_icms_treatment():
    service = ImportNfeService(
        current_user=SimpleNamespace(organization_id=None, id=None)
    )

    authorization = service._authorization_metadata(
        [
            {
                "tax_payload": {
                    "icms": {
                        "cst": "40",
                        "diagnostic_only": True,
                        "tax_treatment_confirmed": False,
                    }
                }
            }
        ]
    )

    assert authorization["ready"] is False
    assert authorization["mode"] == "diagnostic"
    assert authorization["blockers"] == [
        {
            "code": "unconfirmed_icms_tax_treatment",
            "field": "tax_configuration.icms_cst",
            "message": (
                "A assinatura e a transmissão estão bloqueadas até a equipe "
                "fiscal confirmar se a exoneração integral deve usar ICMS CST "
                "40, 41 ou 50."
            ),
        }
    ]


def test_validation_accepts_confirmed_non_taxed_icms_treatment():
    service = ImportNfeService(
        current_user=SimpleNamespace(organization_id=None, id=None)
    )

    authorization = service._authorization_metadata(
        [
            {
                "tax_payload": {
                    "icms": {
                        "cst": "40",
                        "diagnostic_only": False,
                        "tax_treatment_confirmed": True,
                    }
                }
            }
        ]
    )

    assert authorization == {
        "ready": True,
        "blockers": [],
        "mode": "fiscal",
    }
