from app.services.nfe_context import NfeContextResolver
from app.services.import_process import ImportNfeService


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


def test_context_uses_controlled_official_references_without_tabx():
    result = NfeContextResolver().resolve(
        normalized={
            "registration_date": "2026-05-26",
            "clearance_location_code": "0927800",
            "clearance_date": "2026-05-27",
            "transport_mode_code": "4",
            "foreign_supplier": {"country_iso_alpha_2": "US"},
        }
    )

    assert result["ready_for_draft"] is True
    assert result["normalized"]["clearance_location"] == "ALF/PORTO DE ITAJAI"
    assert result["normalized"]["clearance_state"] == "SC"
    assert result["normalized"]["foreign_supplier"]["country_code"] == "2496"
    assert result["fields"]["clearance_location"]["source"] == (
        "builtin_official_reference"
    )


def test_context_resolves_hafele_official_references_and_duimp_costs():
    result = NfeContextResolver().resolve(
        normalized={
            "registration_date": "2026-05-27",
            "clearance_location_code": "0917900",
            "clearance_date": "2026-05-27",
            "transport_mode_code": "1",
            "afrmm_value": "0",
            "tax_totals": {
                "taxa_utilizacao": {"value": "285.34"},
            },
            "foreign_supplier": {"country_iso_alpha_2": "DE"},
        }
    )

    assert result["ready_for_draft"] is True
    assert result["normalized"]["clearance_location"] == "TCP - TERMINAL"
    assert result["normalized"]["clearance_state"] == "PR"
    assert result["normalized"]["foreign_supplier"]["country_code"] == "0230"
    assert result["normalized"]["foreign_supplier"]["country_name"] == "ALEMANHA"
    assert result["suggested"]["additional_costs"] == {
        "afrmm": "0",
        "siscomex_fee": "285.34",
    }


def test_cargo_identifier_prefers_air_waybill_over_ruc():
    identifier = ImportNfeService._cargo_identifier(
        {
            "raw": {
                "dadosGerais": {
                    "carga": {"identificacao": "6BR-RUC-FALLBACK"},
                    "documentos": {
                        "documentosInstrucao": [
                            {
                                "tipo": {"codigo": "30"},
                                "palavrasChave": [
                                    {"codigo": "1", "valor": "047-35401251/005153"}
                                ],
                            }
                        ]
                    },
                }
            }
        }
    )

    assert identifier == "047-35401251/005153"
