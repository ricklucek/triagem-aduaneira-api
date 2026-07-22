from xml.etree import ElementTree as ET

from app.services.nfe_xml_builder import NfeXmlBuilder


NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}


def payload():
    return {
        "document": {
            "state_code": "41",
            "cnf": "76336237",
            "operation_nature": "Importação",
            "series": "1",
            "number": 14422,
            "issue_datetime": "2026-07-16T11:18:38-03:00",
            "tp_emis": "1",
            "check_digit": "5",
            "environment": "production",
        },
        "issuer": {
            "cnpj": "00000000000191",
            "legal_name": "IMPORTADORA TESTE LTDA",
            "state_registration": "1234567890",
            "tax_regime": "3",
            "address": {
                "street": "Rua de Teste",
                "number": "100",
                "district": "Centro",
                "city_code": "4106902",
                "city_name": "Curitiba",
                "state": "PR",
                "zip_code": "80000000",
                "country_code": "1058",
                "country_name": "Brasil",
            },
        },
        "recipient": {
            "party_type": "foreign",
            "foreign_id": "",
            "legal_name": "FOREIGN SUPPLIER LTD",
            "address": {
                "street": "EXTERIOR",
                "number": "0",
                "district": "EXTERIOR",
                "city_code": "9999999",
                "city_name": "EXTERIOR",
                "state": "EX",
                "country_code": "1600",
                "country_name": "CHINA",
            },
        },
        "duimp": {
            "number": "26BR0000000000-1",
            "api_number": "26BR00000000001",
            "registration_date": "2026-07-14",
            "clearance_location": "0917800 - PORTO DE PARANAGUA",
            "clearance_state": "PR",
            "clearance_date": "2026-07-15",
            "transport_mode_code": "1",
            "intermediation_type": "1",
        },
        "items": [
            {
                "item_number": 1,
                "product_code": "PROD-001",
                "description": "Produto sanitizado para teste",
                "ncm": "87087090",
                "cfop": "3102",
                "commercial_unit": "PECAS",
                "commercial_quantity": "12",
                "commercial_unit_value": "504.5325",
                "taxable_unit": "PECAS",
                "taxable_quantity": "12",
                "taxable_unit_value": "504.5325",
                "product_value": "6054.39",
                "freight_value": "0",
                "insurance_value": "0",
                "discount_value": "0",
                "other_value": "88.82",
                "import_payload": {
                    "afrmm_value": "53.46",
                    "sequence_number": "1",
                    "manufacturer_code": "0000",
                    "exporter_code": "EXP-TESTE-001",
                },
                "tax_payload": {
                    "icms": {
                        "origin": "1", "cst": "90", "base_method": "3",
                        "base": "9686.49", "rate": "12", "value": "1162.38",
                    },
                    "ipi": {"cst": "49", "base": "7144.18", "rate": "3.25", "value": "232.19"},
                    "ii": {"base": "6054.39", "customs_expenses": "0", "value": "1089.79", "iof": "0"},
                    "pis": {"cst": "98", "base": "6054.39", "rate": "3.12", "value": "188.90"},
                    "cofins": {"cst": "98", "base": "6054.39", "rate": "14.37", "value": "870.02"},
                    "ibs_cbs": {
                        "cst": "000", "classification": "000001", "base": "5011.70",
                        "ibs_uf_rate": "0.1", "ibs_uf_value": "5.01",
                        "ibs_mun_rate": "0", "ibs_mun_value": "0", "ibs_value": "5.01",
                        "cbs_rate": "0.9", "cbs_value": "45.11",
                    },
                },
            }
        ],
        "totals": {
            "icms_base": "9686.49", "icms_value": "1162.38", "products_value": "6054.39",
            "freight_value": "0", "insurance_value": "0", "discount_value": "0",
            "ii_value": "1089.79", "ipi_value": "232.19", "pis_value": "188.90",
            "cofins_value": "870.02", "other_value": "88.82", "invoice_value": "9686.49",
            "ibs_cbs_base": "5011.70", "ibs_uf_value": "5.01", "ibs_mun_value": "0",
            "ibs_value": "5.01", "cbs_value": "45.11", "rtc_invoice_value": "7465.19",
        },
        "transport": {"freight_mode": "9"},
        "payment": {"method": "90", "value": "0"},
        "additional_info": {"complementary": "DUIMP de teste sanitizada."},
    }


def test_builds_unsigned_import_nfe_with_foreign_recipient_and_duimp():
    xml = NfeXmlBuilder().build(
        payload(), access_key="41260700000000000191550010000144221763362375"
    )
    root = ET.fromstring(xml)

    assert root.tag == "{http://www.portalfiscal.inf.br/nfe}NFe"
    inf_nfe = root.find("nfe:infNFe", NS)
    assert inf_nfe.attrib["Id"].startswith("NFe41")
    assert root.findtext(".//nfe:dest/nfe:enderDest/nfe:UF", namespaces=NS) == "EX"
    assert root.findtext(".//nfe:DI/nfe:nDI", namespaces=NS) == "26BR00000000001"
    assert root.findtext(".//nfe:ICMS90/nfe:vICMS", namespaces=NS) == "1162.38"
    assert root.findtext(".//nfe:IBSCBS/nfe:cClassTrib", namespaces=NS) == "000001"
    assert root.findtext(".//nfe:total/nfe:vNFTot", namespaces=NS) == "7465.19"
    assert root.find(".//{http://www.w3.org/2000/09/xmldsig#}Signature") is None
