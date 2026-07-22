from decimal import Decimal

from app.services.import_tax_calculator import ImportTaxCalculator


def reference_item():
    return {
        "product_value": "6054.39",
        "freight_value": "0",
        "insurance_value": "0",
        "discount_value": "0",
        "other_value": "0",
        "tax_classification_code": "000001",
        "tax_payload": {
            "ii": {"base": "6054.39", "rate": "18", "value": "1089.79"},
            "ipi": {"base": "7144.18", "rate": "3.25", "value": "232.19"},
            "pis": {"base": "6054.39", "rate": "3.12", "value": "188.90"},
            "cofins": {
                "base": "6054.39",
                "rate": "14.37",
                "value": "870.02",
            },
        },
        "import_payload": {},
    }


def configuration():
    return {
        "icms_rate": "12",
        "icms_origin": "1",
        "icms_cst": "90",
        "ipi_cst": "49",
        "pis_cst": "98",
        "cofins_cst": "98",
        "ibs_cbs_cst": "000",
        "tax_classification_code": "000001",
        "ibs_uf_rate": "0.1",
        "ibs_mun_rate": "0",
        "cbs_rate": "0.9",
    }


def test_reproduces_reference_import_tax_bases_for_first_item():
    items, totals = ImportTaxCalculator().calculate(
        [reference_item()],
        configuration=configuration(),
        additional_costs={"afrmm": "53.46", "other": "35.36"},
    )

    item = items[0]
    assert item["other_value"] == "88.82"
    assert item["import_payload"]["afrmm_value"] == "53.46"
    assert item["tax_payload"]["icms"]["base"] == "9686.49"
    assert item["tax_payload"]["icms"]["value"] == "1162.38"
    assert item["tax_payload"]["ibs_cbs"]["base"] == "5011.70"
    assert item["tax_payload"]["ibs_cbs"]["ibs_uf_value"] == "5.01"
    assert item["tax_payload"]["ibs_cbs"]["cbs_value"] == "45.11"
    assert totals["invoice_value"] == "9686.49"
    assert totals["rtc_invoice_value"] == "7465.19"


def test_allocates_costs_and_puts_rounding_remainder_in_last_item():
    calculator = ImportTaxCalculator()
    allocations = calculator.allocate(
        Decimal("10.00"), [Decimal("1"), Decimal("1"), Decimal("1")]
    )
    assert allocations == [Decimal("3.33"), Decimal("3.33"), Decimal("3.34")]
