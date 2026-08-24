import pytest

from app.cnpj import (
    calculate_cnpj_check_digits,
    is_valid_cnpj,
    normalize_cnpj,
)


@pytest.mark.parametrize(
    ("raw_value", "normalized"),
    [
        ("08.266.216/0001-05", "08266216000105"),
        ("03.114.340/0001-31", "03114340000131"),
        ("12.abc.345/01de-35", "12ABC34501DE35"),
    ],
)
def test_normalize_and_validate_cnpj(raw_value, normalized):
    assert normalize_cnpj(raw_value) == normalized
    assert is_valid_cnpj(raw_value) is True


@pytest.mark.parametrize(
    "value",
    [
        "00000000000000",
        "08266216000104",
        "12ABC34501DE34",
        "12ABC34501DE3A",
        "CNPJ-INVALIDO",
    ],
)
def test_reject_invalid_cnpj(value):
    assert is_valid_cnpj(value) is False


def test_calculate_alphanumeric_cnpj_check_digits():
    assert calculate_cnpj_check_digits("12ABC34501DE") == "35"
