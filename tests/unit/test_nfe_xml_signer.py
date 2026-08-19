from datetime import datetime, timedelta, timezone

import pytest
from app.services.fiscal_certificate import (
    FiscalCertificateError,
)
from app.services.nfe_xml_builder import NfeXmlBuilder
from app.services.nfe_xml_signer import NfeXmlSignatureError, NfeXmlSigner
from app.services.nfe_xsd_validator import NfeXsdValidator

from tests.helpers import certificate_material
from tests.unit.test_nfe_xml_builder import payload


def unsigned_xml() -> str:
    return NfeXmlBuilder().build(
        payload(),
        access_key="41260700000000000191550010000144221763362375",
    )


def test_signs_verifies_and_validates_nfe_with_a1_certificate():
    cnpj = "00000000000191"
    signer = NfeXmlSigner()

    result = signer.sign(
        unsigned_xml(),
        material=certificate_material(cnpj),
        expected_cnpj=cnpj,
    )

    assert "<Signature" in result.signed_xml
    assert "<X509Certificate>" in result.signed_xml
    assert result.unsigned_checksum_sha256 != result.signed_checksum_sha256
    signer.verify(result.signed_xml, expected_cnpj=cnpj)
    xsd = NfeXsdValidator().validate(result.signed_xml)
    assert xsd.is_valid is True
    assert xsd.errors == []


def test_rejects_certificate_from_another_cnpj():
    with pytest.raises(
        FiscalCertificateError,
        match="não corresponde ao emitente",
    ):
        NfeXmlSigner().sign(
            unsigned_xml(),
            material=certificate_material("11111111000191"),
            expected_cnpj="00000000000191",
        )


def test_detects_xml_changed_after_signature():
    cnpj = "00000000000191"
    signer = NfeXmlSigner()
    signed = signer.sign(
        unsigned_xml(),
        material=certificate_material(cnpj),
        expected_cnpj=cnpj,
    ).signed_xml
    tampered = signed.replace(
        "<vProd>6054.39</vProd>",
        "<vProd>6054.40</vProd>",
        1,
    )
    assert tampered != signed

    with pytest.raises(NfeXmlSignatureError, match="DigestValue"):
        signer.verify(tampered, expected_cnpj=cnpj)


def test_rejects_expired_a1_certificate():
    now = datetime.now(timezone.utc)
    with pytest.raises(FiscalCertificateError, match="vencido"):
        NfeXmlSigner().sign(
            unsigned_xml(),
            material=certificate_material(
                "00000000000191",
                valid_from=now - timedelta(days=30),
                valid_until=now - timedelta(days=1),
            ),
            expected_cnpj="00000000000191",
        )
