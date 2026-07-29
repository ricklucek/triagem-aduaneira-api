from decimal import Decimal

import pytest

from app.services.duimp_normalizer import DuimpNormalizer


def portal_payload():
    return {
        "provider": "portal_unico",
        "numero": "26BR0000000000-1",
        "versao": "1",
        "dadosGerais": {
            "identificacao": {
                "numero": "26BR00000000001",
                "versao": "1",
                "dataRegistro": "2026-07-14T17:33:00-0300",
                "importador": {"tipoImportador": "CNPJ", "ni": "00000000000191"},
            },
            "carga": {
                "unidadeDeclarada": {"codigo": "0917800", "uf": "PR"},
                "paisProcedencia": {"codigo": "CN", "descricao": "China"},
                "multiplosConhecimentosCarga": {
                    "cargasReferenciadas": [
                        {"dadosAfrmmTum": {"valorDevido": 12.34}}
                    ]
                },
            },
            "quantidadeItens": 1,
            "tributos": {
                "tributosCalculados": [
                    {
                        "tipo": "II",
                        "valoresBRL": {"devido": 180},
                        "memoriaCalculo": {"baseCalculoBRL": 1000},
                    }
                ]
            },
        },
        "itens": [
            {
                "identificacao": {
                    "numero": "26BR00000000001",
                    "versao": "1",
                    "numeroItem": 1,
                },
                "produto": {
                    "codigo": 215,
                    "versao": "1",
                    "ncm": "87087090",
                    "descricao": "Roda automotiva",
                },
                "caracterizacaoImportacao": {"indicador": "IMPORTACAO_DIRETA"},
                "mercadoria": {
                    "unidadeComercial": "PECAS",
                    "quantidadeComercial": 12,
                    "pesoLiquido": 25.5,
                    "descricao": "Modelo de teste",
                },
                "condicaoVenda": {
                    "valorBRL": 900,
                    "frete": {"valorBRL": 90},
                    "seguro": {"valorBRL": 10},
                },
                "exportador": {
                    "codigo": "EXP-1",
                    "nome": "Fornecedor Exterior",
                    "pais": {"codigo": "CN", "descricao": "China"},
                },
                "fabricante": {"codigo": "FAB-1"},
                "tributos": {
                    "mercadoria": {"valorAduaneiroBRL": 1000},
                    "tributosCalculados": [
                        {
                            "tipo": "II",
                            "valoresBRL": {"devido": 180},
                            "memoriaCalculo": {
                                "baseCalculoBRL": 1000,
                                "valorAliquota": 18,
                            },
                        }
                    ],
                },
                "cClassTrib": "000001",
            }
        ],
    }


def test_normalizes_official_portal_payload_using_customs_value():
    result = DuimpNormalizer().normalize(portal_payload())

    assert result["number"] == "26BR0000000000-1"
    assert result["api_number"] == "26BR00000000001"
    assert result["registration_date"] == "2026-07-14"
    assert result["clearance_location_code"] == "0917800"
    assert result["clearance_state"] == "PR"
    assert result["afrmm_value"] == "12.34"
    assert result["import_modality"] == "direct"
    assert result["foreign_supplier"]["name"] == "Fornecedor Exterior"
    assert result["tax_totals"]["ii"]["value"] == "180"

    item = result["items"][0]
    assert item["customs_value"] == "1000"
    assert item["product_value"] == "1000"
    assert Decimal(item["unit_value"]) == Decimal("83.33333333333333333333333333")
    assert item["freight_value"] == "0"
    assert item["insurance_value"] == "0"
    assert item["customs_freight_value"] == "90"
    assert item["customs_insurance_value"] == "10"
    assert item["net_weight"] == "25.5"
    assert item["taxes"]["ii"] == {
        "value": "180",
        "base": "1000",
        "rate": "18",
        "calculation": {"baseCalculoBRL": 1000, "valorAliquota": 18},
        "raw": {
            "tipo": "II",
            "valoresBRL": {"devido": 180},
            "memoriaCalculo": {"baseCalculoBRL": 1000, "valorAliquota": 18},
        },
    }
    assert item["tax_classification_code"] == "000001"


def test_rejects_mixed_modalities_in_same_duimp():
    payload = portal_payload()
    second = dict(payload["itens"][0])
    second["identificacao"] = {"numeroItem": 2}
    second["caracterizacaoImportacao"] = {
        "indicador": "IMPORTACAO_POR_ENCOMENDA",
        "ni": "00000000000272",
    }
    payload["itens"].append(second)

    try:
        DuimpNormalizer().normalize(payload)
    except ValueError as exc:
        assert "modalidades de importação diferentes" in str(exc)
    else:
        raise AssertionError("Era esperado ValueError para modalidades diferentes")


@pytest.mark.parametrize(
    ("portal_value", "expected"),
    [
        ("IMPORTACAO_DIRETA", "direct"),
        ("IMPORTACAO_POR_CONTA_E_ORDEM", "on_behalf"),
        ("IMPORTACAO_POR_ENCOMENDA", "by_order"),
    ],
)
def test_maps_supported_import_modalities(portal_value, expected):
    payload = portal_payload()
    payload["itens"][0]["caracterizacaoImportacao"] = {
        "indicador": portal_value,
        "ni": "00000000000272" if expected != "direct" else None,
    }

    result = DuimpNormalizer().normalize(payload)

    assert result["import_modality"] == expected
    if expected != "direct":
        assert result["third_party_tax_id"] == "00000000000272"
