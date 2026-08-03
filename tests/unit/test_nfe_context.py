from app.services.nfe_context import NfeContextResolver


def test_context_resolver_combines_official_sources_and_explicit_overrides():
    resolver = NfeContextResolver()
    normalized = {
        "registration_date": "2026-05-26",
        "clearance_location_code": "0927800",
        "clearance_location": None,
        "clearance_state": None,
        "clearance_date": None,
        "transport_mode_code": None,
        "foreign_supplier": {"country_iso_alpha_2": "US"},
    }
    external = {
        "cargo_knowledge": [
            {
                "situacao": "A",
                "tipo": "AWB",
                "codigoAeroportoDestinoConhecimento": "CWB",
            }
        ],
        "customs_unit": {
            "dados": [
                {
                    "campos": [
                        {"nome": "NOME", "valor": "AEROPORTO DE CURITIBA"},
                        {"nome": "UF", "valor": "PR"},
                    ]
                }
            ]
        },
        "country": {
            "dados": [
                {
                    "campos": [
                        {"nome": "CODIGO", "valor": "2496"},
                        {"nome": "NOME", "valor": "ESTADOS UNIDOS"},
                    ]
                }
            ]
        },
        "icms_declaration": {
            "valorAfrmm": 0,
            "valorDespesasAduaneiras": 123.45,
        },
    }

    result = resolver.resolve(
        normalized=normalized,
        external=external,
        overrides={"clearance_date": "2026-05-30", "unknown": "ignored"},
    )

    assert result["ready_for_draft"] is True
    assert result["normalized"]["clearance_location"] == "AEROPORTO DE CURITIBA"
    assert result["normalized"]["clearance_state"] == "PR"
    assert result["normalized"]["transport_mode_code"] == "4"
    assert result["normalized"]["clearance_date"] == "2026-05-30"
    assert result["normalized"]["foreign_supplier"]["country_code"] == "2496"
    assert result["fields"]["clearance_location"]["source"] == "portal_unico_tabx"
    assert result["fields"]["clearance_date"]["source"] == "operator_override"
    assert result["suggested"]["additional_costs"] == {
        "afrmm": "0",
        "other": "123.45",
    }
    assert "unknown" not in result["normalized"]


def test_context_resolver_keeps_unconfirmed_fields_missing():
    result = NfeContextResolver().resolve(
        normalized={
            "registration_date": "2026-05-26",
            "foreign_supplier": {},
        }
    )

    assert result["ready_for_draft"] is False
    assert "clearance_date" in result["missing_fields"]
    assert "foreign_supplier.country_code" in result["missing_fields"]
    assert result["fields"]["clearance_date"] == {
        "value": None,
        "source": None,
        "status": "missing",
    }
