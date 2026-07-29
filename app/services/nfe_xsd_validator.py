from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from lxml import etree


class NfeXsdConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class NfeXsdValidationResult:
    is_valid: bool
    errors: list[dict[str, Any]]
    schema_package: str
    schema_file: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.is_valid,
            "errors": self.errors,
            "schema": {
                "package": self.schema_package,
                "file": self.schema_file,
            },
        }


class NfeXsdValidator:
    """Valida NF-e 4.00 com o pacote oficial PL_010e_v1.02."""

    SCHEMA_PACKAGE = "PL_010e_v1.02"
    DEFAULT_SCHEMA_PATH = (
        Path(__file__).resolve().parent.parent
        / "resources"
        / "nfe_schemas"
        / SCHEMA_PACKAGE
        / "nfe_v4.00.xsd"
    )

    NFE_NS = "http://www.portalfiscal.inf.br/nfe"
    DS_NS = "http://www.w3.org/2000/09/xmldsig#"

    def __init__(self, schema_path: str | Path | None = None):
        self.schema_path = Path(schema_path or self.DEFAULT_SCHEMA_PATH)

    def validate(
        self,
        xml_content: str,
        *,
        allow_unsigned: bool = False,
    ) -> NfeXsdValidationResult:
        schema = self._schema()
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
            return self._result(
                False,
                [
                    {
                        "line": exc.lineno,
                        "column": exc.position[1] if exc.position else None,
                        "domain": "PARSER",
                        "type": "XML_SYNTAX_ERROR",
                        "level": "ERROR",
                        "message": str(exc).split(", line ", 1)[0],
                    }
                ],
            )

        validation_root = deepcopy(root)
        if allow_unsigned:
            self._add_validation_signature_if_missing(validation_root)

        document = etree.ElementTree(validation_root)
        is_valid = schema.validate(document)
        errors = [
            {
                "line": error.line,
                "column": error.column,
                "domain": error.domain_name,
                "type": error.type_name,
                "level": error.level_name,
                "message": error.message,
            }
            for error in schema.error_log
        ]
        return self._result(is_valid, errors)

    def _schema(self) -> etree.XMLSchema:
        resolved_path = self.schema_path.expanduser().resolve()
        if not resolved_path.is_file():
            raise NfeXsdConfigurationError(
                f"O pacote XSD {self.SCHEMA_PACKAGE} não está disponível."
            )
        try:
            return self._load_schema(str(resolved_path))
        except (OSError, etree.XMLSchemaParseError, etree.XMLSyntaxError) as exc:
            raise NfeXsdConfigurationError(
                f"Não foi possível carregar o pacote XSD {self.SCHEMA_PACKAGE}."
            ) from exc

    @staticmethod
    @lru_cache(maxsize=4)
    def _load_schema(schema_path: str) -> etree.XMLSchema:
        parser = etree.XMLParser(
            resolve_entities=False,
            load_dtd=False,
            no_network=True,
        )
        return etree.XMLSchema(etree.parse(schema_path, parser=parser))

    def _result(
        self,
        is_valid: bool,
        errors: list[dict[str, Any]],
    ) -> NfeXsdValidationResult:
        return NfeXsdValidationResult(
            is_valid=is_valid,
            errors=errors,
            schema_package=self.SCHEMA_PACKAGE,
            schema_file=self.schema_path.name,
        )

    def _add_validation_signature_if_missing(
        self,
        root: etree._Element,
    ) -> None:
        if etree.QName(root).namespace != self.NFE_NS:
            return
        if etree.QName(root).localname != "NFe":
            return
        if root.find(f"{{{self.DS_NS}}}Signature") is not None:
            return

        inf_nfe = root.find(f"{{{self.NFE_NS}}}infNFe")
        if inf_nfe is None or not inf_nfe.get("Id"):
            return

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

        signature = element(root, "Signature")
        signed_info = element(signature, "SignedInfo")
        element(
            signed_info,
            "CanonicalizationMethod",
            Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
        )
        element(
            signed_info,
            "SignatureMethod",
            Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1",
        )
        reference = element(
            signed_info,
            "Reference",
            URI=f"#{inf_nfe.get('Id')}",
        )
        transforms = element(reference, "Transforms")
        element(
            transforms,
            "Transform",
            Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature",
        )
        element(
            transforms,
            "Transform",
            Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
        )
        element(
            reference,
            "DigestMethod",
            Algorithm="http://www.w3.org/2000/09/xmldsig#sha1",
        )
        element(reference, "DigestValue", "AA==")
        element(signature, "SignatureValue", "AA==")
        key_info = element(signature, "KeyInfo")
        x509_data = element(key_info, "X509Data")
        element(x509_data, "X509Certificate", "AA==")
