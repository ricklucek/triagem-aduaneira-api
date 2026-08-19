from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree

from app.services.fiscal_certificate import (
    A1CertificateInspector,
    CertificateMaterial,
    FiscalCertificateError,
    LoadedA1Certificate,
)


class NfeXmlSignatureError(ValueError):
    """Falha de contrato, certificado ou verificação da XMLDSig."""


@dataclass(frozen=True)
class NfeXmlSignatureResult:
    signed_xml: str
    certificate: LoadedA1Certificate
    unsigned_checksum_sha256: str
    signed_checksum_sha256: str


class NfeXmlSigner:
    NFE_NS = "http://www.portalfiscal.inf.br/nfe"
    DS_NS = "http://www.w3.org/2000/09/xmldsig#"
    CANONICALIZATION_ALGORITHM = (
        "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
    )
    SIGNATURE_ALGORITHM = "http://www.w3.org/2000/09/xmldsig#rsa-sha1"
    DIGEST_ALGORITHM = "http://www.w3.org/2000/09/xmldsig#sha1"
    ENVELOPED_SIGNATURE_ALGORITHM = (
        "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
    )

    def __init__(
        self,
        *,
        certificate_inspector: A1CertificateInspector | None = None,
    ) -> None:
        self.certificate_inspector = (
            certificate_inspector or A1CertificateInspector()
        )

    def sign(
        self,
        xml_content: str,
        *,
        material: CertificateMaterial,
        expected_cnpj: str,
    ) -> NfeXmlSignatureResult:
        root = self._parse(xml_content)
        inf_nfe = self._inf_nfe(root)
        identifier = str(inf_nfe.get("Id") or "")
        if not re.fullmatch(r"NFe[0-9]{44}", identifier):
            raise NfeXmlSignatureError(
                "O atributo Id de infNFe deve conter NFe seguido da chave de 44 dígitos."
            )
        issuer_cnpj = root.findtext(
            f".//{{{self.NFE_NS}}}emit/{{{self.NFE_NS}}}CNPJ"
        )
        if self._digits(issuer_cnpj) != self._digits(expected_cnpj):
            raise NfeXmlSignatureError(
                "O CNPJ do XML não corresponde ao emitente esperado."
            )
        if root.find(f"{{{self.DS_NS}}}Signature") is not None:
            raise NfeXmlSignatureError(
                "A versão XML informada já contém uma assinatura."
            )
        loaded = self.certificate_inspector.load(
            material,
            expected_cnpj=expected_cnpj,
        )

        digest_value = base64.b64encode(
            hashlib.sha1(self._canonicalize(inf_nfe)).digest()
        ).decode("ascii")
        signature = self._signature_element(
            root,
            identifier=identifier,
            digest_value=digest_value,
            certificate=loaded.certificate,
        )
        signed_info = signature.find(f"{{{self.DS_NS}}}SignedInfo")
        signature_bytes = loaded.private_key.sign(
            self._canonicalize(signed_info),
            padding.PKCS1v15(),
            hashes.SHA1(),
        )
        signature.find(
            f"{{{self.DS_NS}}}SignatureValue"
        ).text = base64.b64encode(signature_bytes).decode("ascii")

        signed_xml = etree.tostring(
            root,
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=False,
        ).decode("utf-8")
        self.verify(signed_xml, expected_cnpj=expected_cnpj)
        return NfeXmlSignatureResult(
            signed_xml=signed_xml,
            certificate=loaded,
            unsigned_checksum_sha256=self._sha256(xml_content),
            signed_checksum_sha256=self._sha256(signed_xml),
        )

    def verify(
        self,
        signed_xml: str,
        *,
        expected_cnpj: str,
    ) -> None:
        root = self._parse(signed_xml)
        inf_nfe = self._inf_nfe(root)
        signature = root.find(f"{{{self.DS_NS}}}Signature")
        if signature is None:
            raise NfeXmlSignatureError(
                "O XML não contém o grupo Signature."
            )
        reference = signature.find(
            f"./{{{self.DS_NS}}}SignedInfo/{{{self.DS_NS}}}Reference"
        )
        if reference is None or reference.get("URI") != f"#{inf_nfe.get('Id')}":
            raise NfeXmlSignatureError(
                "A assinatura não referencia o infNFe informado."
            )

        digest_node = reference.find(f"{{{self.DS_NS}}}DigestValue")
        expected_digest = base64.b64encode(
            hashlib.sha1(self._canonicalize(inf_nfe)).digest()
        ).decode("ascii")
        if digest_node is None or digest_node.text != expected_digest:
            raise NfeXmlSignatureError(
                "O DigestValue da assinatura não corresponde ao infNFe."
            )

        certificate_node = signature.find(
            f".//{{{self.DS_NS}}}X509Certificate"
        )
        signature_value_node = signature.find(
            f"{{{self.DS_NS}}}SignatureValue"
        )
        signed_info = signature.find(f"{{{self.DS_NS}}}SignedInfo")
        if (
            certificate_node is None
            or not certificate_node.text
            or signature_value_node is None
            or not signature_value_node.text
            or signed_info is None
        ):
            raise NfeXmlSignatureError(
                "A assinatura XML está incompleta."
            )
        try:
            certificate = x509.load_der_x509_certificate(
                base64.b64decode(certificate_node.text, validate=True)
            )
            certificate_cnpj = self.certificate_inspector.extract_cnpj(
                certificate
            )
            if certificate_cnpj != self._digits(expected_cnpj):
                raise NfeXmlSignatureError(
                    "O certificado embutido não pertence ao emitente."
                )
            certificate.public_key().verify(
                base64.b64decode(signature_value_node.text, validate=True),
                self._canonicalize(signed_info),
                padding.PKCS1v15(),
                hashes.SHA1(),
            )
        except NfeXmlSignatureError:
            raise
        except (
            InvalidSignature,
            ValueError,
            TypeError,
            FiscalCertificateError,
        ) as exc:
            raise NfeXmlSignatureError(
                "A verificação criptográfica da assinatura XML falhou."
            ) from exc

    def _signature_element(
        self,
        root: etree._Element,
        *,
        identifier: str,
        digest_value: str,
        certificate: x509.Certificate,
    ) -> etree._Element:
        def element(
            parent: etree._Element,
            name: str,
            text: str | None = None,
            **attributes: str,
        ) -> etree._Element:
            node = etree.SubElement(
                parent,
                f"{{{self.DS_NS}}}{name}",
                **attributes,
            )
            node.text = text
            return node

        signature = etree.SubElement(
            root,
            f"{{{self.DS_NS}}}Signature",
            nsmap={None: self.DS_NS},
        )
        signed_info = element(signature, "SignedInfo")
        element(
            signed_info,
            "CanonicalizationMethod",
            Algorithm=self.CANONICALIZATION_ALGORITHM,
        )
        element(
            signed_info,
            "SignatureMethod",
            Algorithm=self.SIGNATURE_ALGORITHM,
        )
        reference = element(
            signed_info,
            "Reference",
            URI=f"#{identifier}",
        )
        transforms = element(reference, "Transforms")
        element(
            transforms,
            "Transform",
            Algorithm=self.ENVELOPED_SIGNATURE_ALGORITHM,
        )
        element(
            transforms,
            "Transform",
            Algorithm=self.CANONICALIZATION_ALGORITHM,
        )
        element(
            reference,
            "DigestMethod",
            Algorithm=self.DIGEST_ALGORITHM,
        )
        element(reference, "DigestValue", digest_value)
        element(signature, "SignatureValue")
        key_info = element(signature, "KeyInfo")
        x509_data = element(key_info, "X509Data")
        certificate_der = certificate.public_bytes(serialization.Encoding.DER)
        element(
            x509_data,
            "X509Certificate",
            base64.b64encode(certificate_der).decode("ascii"),
        )
        return signature

    def _parse(self, xml_content: str) -> etree._Element:
        parser = etree.XMLParser(
            resolve_entities=False,
            load_dtd=False,
            no_network=True,
            remove_blank_text=False,
        )
        try:
            root = etree.fromstring(
                str(xml_content or "").encode("utf-8"),
                parser=parser,
            )
        except etree.XMLSyntaxError as exc:
            raise NfeXmlSignatureError(
                "O XML informado não está bem formado."
            ) from exc
        if (
            etree.QName(root).namespace != self.NFE_NS
            or etree.QName(root).localname != "NFe"
        ):
            raise NfeXmlSignatureError(
                "A raiz do documento deve ser NFe no namespace oficial."
            )
        return root

    def _inf_nfe(self, root: etree._Element) -> etree._Element:
        inf_nfe = root.find(f"{{{self.NFE_NS}}}infNFe")
        if inf_nfe is None:
            raise NfeXmlSignatureError(
                "O XML não contém o elemento infNFe."
            )
        return inf_nfe

    @staticmethod
    def _canonicalize(element: etree._Element) -> bytes:
        return etree.tostring(
            element,
            method="c14n",
            exclusive=False,
            with_comments=False,
        )

    @staticmethod
    def _sha256(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _digits(value: str | None) -> str:
        return "".join(
            character
            for character in str(value or "")
            if character.isdigit()
        )
