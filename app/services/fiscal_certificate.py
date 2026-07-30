from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID, ObjectIdentifier


class FiscalCertificateError(ValueError):
    """Falha segura ao resolver ou validar um certificado fiscal A1."""


@dataclass(frozen=True)
class CertificateMaterial:
    pkcs12_bytes: bytes
    password: bytes


@dataclass(frozen=True)
class LoadedA1Certificate:
    private_key: rsa.RSAPrivateKey
    certificate: x509.Certificate
    issuer_cnpj: str
    fingerprint_sha256: str
    serial_number: str
    subject_name: str
    valid_from: datetime
    valid_until: datetime


class CertificateVault(Protocol):
    def resolve(
        self,
        *,
        provider: str,
        certificate_ref: str,
        password_ref: str,
    ) -> CertificateMaterial:
        ...


class EnvironmentCertificateVault:
    """Resolver de desenvolvimento sem persistir o A1 no banco.

    ``certificate_ref=env:NFE_CLIENT_CERTIFICATE_PFX_BASE64`` lê um PKCS#12
    codificado em Base64. ``password_ref=env:NFE_CLIENT_CERTIFICATE_PASSWORD``
    lê a senha em texto a partir do ambiente do container.
    """

    _ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")

    def resolve(
        self,
        *,
        provider: str,
        certificate_ref: str,
        password_ref: str,
    ) -> CertificateMaterial:
        del provider
        certificate_name = self._environment_name(certificate_ref)
        password_name = self._environment_name(password_ref)
        encoded_certificate = os.getenv(certificate_name, "")
        password = os.getenv(password_name)
        if not encoded_certificate:
            raise FiscalCertificateError(
                "A variável de ambiente do certificado A1 está vazia."
            )
        if password is None:
            raise FiscalCertificateError(
                "A variável de ambiente da senha do certificado A1 não existe."
            )
        try:
            pkcs12_bytes = base64.b64decode(
                encoded_certificate,
                validate=True,
            )
        except (ValueError, TypeError) as exc:
            raise FiscalCertificateError(
                "O certificado A1 do ambiente não contém Base64 válido."
            ) from exc
        if not pkcs12_bytes:
            raise FiscalCertificateError(
                "O certificado A1 resolvido está vazio."
            )
        return CertificateMaterial(
            pkcs12_bytes=pkcs12_bytes,
            password=password.encode("utf-8"),
        )

    def _environment_name(self, reference: str) -> str:
        value = str(reference or "")
        if not value.startswith("env:"):
            raise FiscalCertificateError(
                "A referência local do certificado deve começar com env:."
            )
        name = value.removeprefix("env:").strip()
        if not self._ENV_NAME.fullmatch(name):
            raise FiscalCertificateError(
                "A referência local contém um nome de variável inválido."
            )
        return name


class GcpSecretManagerCertificateVault:
    """Resolve PKCS#12 e senha em secrets distintos do Secret Manager.

    As referências aceitas são ``gcp:NOME`` ou ``gcp:NOME@VERSAO``. Quando a
    versão não é informada, ``latest`` é usado. O secret do certificado deve
    conter os bytes originais do arquivo PFX/P12; o secret da senha contém
    texto UTF-8.
    """

    _SECRET_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
    _VERSION = re.compile(r"^[1-9][0-9]*$|^latest$")

    def __init__(
        self,
        *,
        client: Any | None = None,
        project_id: str | None = None,
    ) -> None:
        self._client = client
        self.project_id = (
            project_id
            or os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GCP_PROJECT_ID")
        )

    def resolve(
        self,
        *,
        provider: str,
        certificate_ref: str,
        password_ref: str,
    ) -> CertificateMaterial:
        del provider
        if not self.project_id:
            raise FiscalCertificateError(
                "GOOGLE_CLOUD_PROJECT ou GCP_PROJECT_ID é obrigatório."
            )
        certificate_resource = self._resource_name(certificate_ref)
        password_resource = self._resource_name(password_ref)
        pkcs12_bytes = self._access_secret(certificate_resource)
        password_bytes = self._access_secret(password_resource).rstrip(b"\r\n")
        if not pkcs12_bytes:
            raise FiscalCertificateError(
                "O secret do certificado A1 está vazio."
            )
        if not password_bytes:
            raise FiscalCertificateError(
                "O secret da senha do certificado A1 está vazio."
            )
        return CertificateMaterial(
            pkcs12_bytes=pkcs12_bytes,
            password=password_bytes,
        )

    def _resource_name(self, reference: str) -> str:
        value = str(reference or "")
        if not value.startswith("gcp:"):
            raise FiscalCertificateError(
                "A referência do Secret Manager deve começar com gcp:."
            )
        identifier = value.removeprefix("gcp:").strip()
        secret_id, separator, version = identifier.partition("@")
        version = version if separator else "latest"
        if not self._SECRET_ID.fullmatch(secret_id):
            raise FiscalCertificateError(
                "A referência contém um nome de secret inválido."
            )
        if not self._VERSION.fullmatch(version):
            raise FiscalCertificateError(
                "A versão do secret deve ser um número positivo ou latest."
            )
        return (
            f"projects/{self.project_id}/secrets/{secret_id}/versions/{version}"
        )

    def _access_secret(self, resource_name: str) -> bytes:
        try:
            response = self._secret_manager_client().access_secret_version(
                request={"name": resource_name}
            )
            return bytes(response.payload.data)
        except Exception as exc:
            raise FiscalCertificateError(
                "Não foi possível acessar um secret do certificado A1."
            ) from exc

    def _secret_manager_client(self) -> Any:
        if self._client is None:
            try:
                from google.cloud import secretmanager
            except ImportError as exc:
                raise FiscalCertificateError(
                    "A dependência google-cloud-secret-manager não está instalada."
                ) from exc
            self._client = secretmanager.SecretManagerServiceClient()
        return self._client


class DefaultCertificateVault:
    def __init__(
        self,
        *,
        environment_vault: CertificateVault | None = None,
        gcp_vault: CertificateVault | None = None,
    ) -> None:
        self.environment_vault = (
            environment_vault or EnvironmentCertificateVault()
        )
        self.gcp_vault = (
            gcp_vault or GcpSecretManagerCertificateVault()
        )

    def resolve(
        self,
        *,
        provider: str,
        certificate_ref: str,
        password_ref: str,
    ) -> CertificateMaterial:
        if str(provider) not in {
            "gcp_secret_manager",
            "FiscalCredentialProvider.GCP_SECRET_MANAGER",
        }:
            raise FiscalCertificateError(
                "O provider do certificado ainda não é suportado para assinatura."
            )
        if certificate_ref.startswith("env:") and password_ref.startswith(
            "env:"
        ):
            return self.environment_vault.resolve(
                provider=provider,
                certificate_ref=certificate_ref,
                password_ref=password_ref,
            )
        if certificate_ref.startswith("gcp:") and password_ref.startswith(
            "gcp:"
        ):
            return self.gcp_vault.resolve(
                provider=provider,
                certificate_ref=certificate_ref,
                password_ref=password_ref,
            )
        raise FiscalCertificateError(
            "Certificado e senha devem usar o mesmo provider env: ou gcp:."
        )


class A1CertificateInspector:
    CNPJ_OID = ObjectIdentifier("2.16.76.1.3.3")
    _CNPJ = re.compile(r"(?<!\d)(\d{14})(?!\d)")

    def load(
        self,
        material: CertificateMaterial,
        *,
        expected_cnpj: str,
        at: datetime | None = None,
    ) -> LoadedA1Certificate:
        expected = self._digits(expected_cnpj)
        if len(expected) != 14:
            raise FiscalCertificateError(
                "O CNPJ esperado para o certificado deve conter 14 dígitos."
            )
        try:
            private_key, certificate, _ = (
                pkcs12.load_key_and_certificates(
                    material.pkcs12_bytes,
                    material.password,
                )
            )
        except (ValueError, TypeError) as exc:
            raise FiscalCertificateError(
                "O arquivo A1 ou sua senha são inválidos."
            ) from exc
        if certificate is None or private_key is None:
            raise FiscalCertificateError(
                "O PKCS#12 não contém certificado e chave privada."
            )
        if not isinstance(private_key, rsa.RSAPrivateKey):
            raise FiscalCertificateError(
                "A NF-e exige uma chave privada RSA no certificado A1."
            )

        issuer_cnpj = self.extract_cnpj(certificate)
        if issuer_cnpj != expected:
            raise FiscalCertificateError(
                "O CNPJ do certificado A1 não corresponde ao emitente da NF-e."
            )

        now = at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        valid_from = certificate.not_valid_before_utc
        valid_until = certificate.not_valid_after_utc
        if now < valid_from:
            raise FiscalCertificateError(
                "O certificado A1 ainda não está válido."
            )
        if now > valid_until:
            raise FiscalCertificateError(
                "O certificado A1 está vencido."
            )

        try:
            key_usage = certificate.extensions.get_extension_for_class(
                x509.KeyUsage
            ).value
        except x509.ExtensionNotFound:
            key_usage = None
        if key_usage is not None and not key_usage.digital_signature:
            raise FiscalCertificateError(
                "O certificado A1 não permite assinatura digital."
            )

        return LoadedA1Certificate(
            private_key=private_key,
            certificate=certificate,
            issuer_cnpj=issuer_cnpj,
            fingerprint_sha256=certificate.fingerprint(
                hashes.SHA256()
            ).hex(),
            serial_number=str(certificate.serial_number),
            subject_name=certificate.subject.rfc4514_string(),
            valid_from=valid_from,
            valid_until=valid_until,
        )

    def extract_cnpj(self, certificate: x509.Certificate) -> str:
        for attribute in certificate.subject.get_attributes_for_oid(
            self.CNPJ_OID
        ):
            match = self._CNPJ.search(str(attribute.value))
            if match:
                return match.group(1)

        try:
            alternative_names = certificate.extensions.get_extension_for_class(
                x509.SubjectAlternativeName
            ).value
        except x509.ExtensionNotFound:
            alternative_names = None
        if alternative_names is not None:
            for other_name in alternative_names.get_values_for_type(
                x509.OtherName
            ):
                if other_name.type_id != self.CNPJ_OID:
                    continue
                match = re.search(rb"(?<!\d)(\d{14})(?!\d)", other_name.value)
                if match:
                    return match.group(1).decode("ascii")

        for oid in (NameOID.SERIAL_NUMBER, NameOID.COMMON_NAME):
            for attribute in certificate.subject.get_attributes_for_oid(oid):
                match = self._CNPJ.search(str(attribute.value))
                if match:
                    return match.group(1)
        raise FiscalCertificateError(
            "Não foi possível identificar o CNPJ no certificado A1."
        )

    @staticmethod
    def _digits(value: str) -> str:
        return "".join(character for character in str(value or "") if character.isdigit())
