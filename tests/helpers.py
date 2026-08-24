from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID, ObjectIdentifier

from app.services.fiscal_certificate import CertificateMaterial


def certificate_material(
    cnpj: str,
    *,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
) -> CertificateMaterial:
    now = datetime.now(timezone.utc)
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    subject = x509.Name(
        [
            x509.NameAttribute(
                NameOID.COMMON_NAME,
                f"CERTIFICADO TESTE:{cnpj}",
            ),
            x509.NameAttribute(
                ObjectIdentifier("2.16.76.1.3.3"),
                cnpj,
            ),
        ]
    )
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(valid_from or now - timedelta(days=1))
        .not_valid_after(valid_until or now + timedelta(days=30))
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .sign(private_key, hashes.SHA256())
    )
    password = b"senha-segura"
    pfx = pkcs12.serialize_key_and_certificates(
        name=b"nfe-test",
        key=private_key,
        cert=certificate,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password),
    )
    return CertificateMaterial(pkcs12_bytes=pfx, password=password)


class StaticCertificateVault:
    def __init__(self, material: CertificateMaterial) -> None:
        self.material = material

    def resolve(
        self,
        *,
        provider: str,
        certificate_ref: str,
        password_ref: str,
    ) -> CertificateMaterial:
        del provider, certificate_ref, password_ref
        return self.material
