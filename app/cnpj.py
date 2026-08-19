import re
from typing import Any


_CNPJ_MASK = re.compile(r"[.\-/\s]")
_CNPJ_FORMAT = re.compile(r"[A-Z0-9]{12}[0-9]{2}")
_FIRST_DIGIT_WEIGHTS = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_SECOND_DIGIT_WEIGHTS = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def normalize_cnpj(value: Any) -> str:
    """Remove a máscara e preserva letras do CNPJ alfanumérico."""

    return _CNPJ_MASK.sub("", str(value or "").strip()).upper()


def _character_value(character: str) -> int:
    # Regra oficial do CNPJ alfanumérico: código ASCII menos 48.
    return ord(character) - 48


def _check_digit(characters: str, weights: tuple[int, ...]) -> str:
    remainder = sum(
        _character_value(character) * weight
        for character, weight in zip(characters, weights, strict=True)
    ) % 11
    return str(0 if remainder < 2 else 11 - remainder)


def calculate_cnpj_check_digits(base: str) -> str:
    normalized_base = normalize_cnpj(base)
    if not re.fullmatch(r"[A-Z0-9]{12}", normalized_base):
        raise ValueError("A base do CNPJ deve conter 12 caracteres alfanuméricos.")

    first_digit = _check_digit(normalized_base, _FIRST_DIGIT_WEIGHTS)
    second_digit = _check_digit(
        normalized_base + first_digit,
        _SECOND_DIGIT_WEIGHTS,
    )
    return first_digit + second_digit


def is_valid_cnpj(value: Any) -> bool:
    cnpj = normalize_cnpj(value)
    if not _CNPJ_FORMAT.fullmatch(cnpj):
        return False
    if cnpj.isdigit() and len(set(cnpj)) == 1:
        return False
    return cnpj[-2:] == calculate_cnpj_check_digits(cnpj[:12])
