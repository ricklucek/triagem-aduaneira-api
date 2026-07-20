from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from xml.sax.saxutils import escape

from sqlalchemy import or_

from ..extensions import db
from ..models import Client
from ..models import (
    ClientFiscalProfile,
    DuimpSnapshot,
    ExternalApiRequestLog,
    ExternalProvider,
    ExternalProviderConnection,
    FiscalEnvironment,
    HttpMethod,
    ImportProcess,
    ImportProcessSource,
    ImportProcessStatus,
    ImportPurpose,
    NfeDraft,
    NfeDraftItem,
    NfeDraftStatus,
    NfeModel,
    NfeOperationType,
    NfePurpose,
    NfeXmlType,
    NfeXmlVersion,
)

from app.services.nfe_access_key_service import NfeAccessKeyService
from app.services.nfe_number_service import NfeNumberSequenceService


@dataclass
class ValidationResult:
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {"valid": self.is_valid, "errors": self.errors, "warnings": self.warnings}


class MockDuimpGateway:
    """Gateway temporário para desenvolvimento sem dependência do Portal Único."""

    def fetch_duimp(self, *, duimp_number: str, duimp_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if duimp_payload:
            return duimp_payload

        return {
            "numero": duimp_number,
            "versao": "1",
            "dataRegistro": datetime.utcnow().date().isoformat(),
            "localDesembaraco": "PARANAGUA",
            "ufDesembaraco": "PR",
            "dataDesembaraco": datetime.utcnow().date().isoformat(),
            "viaTransporteCodigo": "1",
            "tipoIntermedio": "1",
            "codigoExportador": "EXPORTADOR-EXEMPLO",
            "itens": [
                {
                    "numeroItem": "1",
                    "codigoProduto": "ITEM-1",
                    "descricao": "Produto importado exemplo",
                    "ncm": "85044010",
                    "quantidade": "1.0000",
                    "unidade": "UN",
                    "valorUnitario": "100.0000000000",
                    "valorProduto": "100.00",
                    "numeroAdicao": "1",
                    "sequenciaAdicao": "1",
                    "codigoFabricante": "FABRICANTE-EXEMPLO",
                }
            ],
        }


class ImportNfeService:
    def __init__(self, current_user, duimp_gateway: MockDuimpGateway | None = None):
        self.current_user = current_user
        self.organization_id = getattr(current_user, "organization_id", None)
        self.user_id = getattr(current_user, "id", None)
        self.duimp_gateway = duimp_gateway or MockDuimpGateway()

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def import_process_query_for_current_user(self):
        query = ImportProcess.query
        if self.organization_id:
            query = query.filter(ImportProcess.organization_id == self.organization_id)
        return query

    def provider_connection_query_for_current_user(self):
        query = ExternalProviderConnection.query
        if self.organization_id:
            query = query.filter(ExternalProviderConnection.organization_id == self.organization_id)
        return query

    def nfe_draft_query_for_current_user(self):
        query = NfeDraft.query
        if self.organization_id:
            query = query.filter(NfeDraft.organization_id == self.organization_id)
        return query

    def snapshot_query_for_current_user(self):
        query = DuimpSnapshot.query
        if self.organization_id:
            query = query.filter(DuimpSnapshot.organization_id == self.organization_id)
        return query

    def client_fiscal_profile_query_for_current_user(self):
        query = ClientFiscalProfile.query
        if self.organization_id:
            query = query.filter(ClientFiscalProfile.organization_id == self.organization_id)
        return query
    
    def get_nfe_draft_or_404(self, draft_id) -> NfeDraft:
        draft = self.nfe_draft_query_for_current_user().filter(NfeDraft.id == draft_id).first()
        if not draft:
            raise ValueError("Rascunho fiscal não encontrado.")
        return draft
    
    def generate_access_key_for_draft(self, draft_id):
        draft = self.get_nfe_draft_or_404(draft_id)

        if draft.status not in ["ready_for_xml", "xml_generated", "validation_failed"]:
            raise ValueError(
                f"Status atual do rascunho não permite geração da chave de acesso: {draft.status}"
            )

        validation = self.validate_nfe_draft_payload(draft.fiscal_payload)

        if not validation["valid"]:
            draft.status = "validation_failed"
            draft.validation_errors = validation["errors"]
            draft.validation_warnings = validation["warnings"]
            draft.updated_at = datetime.now()

            raise ValueError(
                "Rascunho fiscal inválido. Corrija os erros antes de gerar a chave de acesso."
            )

        now = datetime.now()

        if not draft.number:
            sequence_service = NfeNumberSequenceService(current_user=self.current_user)

            draft.number = sequence_service.reserve_next_number(
                client_id=draft.importer_id,
                environment=draft.environment,
                model=draft.model,
                series=draft.series,
            )

        access_key_service = NfeAccessKeyService()

        access_key_data = access_key_service.generate_for_draft(
            draft=draft,
            issue_datetime=now,
            tp_emis="1",
        )

        fiscal_payload = draft.fiscal_payload or {}
        document = fiscal_payload.get("document") or {}

        document.update(
            {
                "access_key": access_key_data["access_key"],
                "state_code": access_key_data["cUF"],
                "aamm": access_key_data["AAMM"],
                "cnf": access_key_data["cNF"],
                "check_digit": access_key_data["cDV"],
                "tp_emis": access_key_data["tpEmis"],
                "issue_datetime": now.isoformat(),
                "number": draft.number,
                "series": draft.series,
                "model": draft.model,
            }
        )

        fiscal_payload["document"] = document

        draft.access_key = access_key_data["access_key"]
        draft.fiscal_payload = fiscal_payload
        draft.status = "ready_for_xml"
        draft.validation_errors = []
        draft.validation_warnings = validation["warnings"]
        draft.updated_at = now

        return {
            "draft": draft,
            "access_key": access_key_data,
            "validation": validation,
        }

    # ------------------------------------------------------------------
    # Client fiscal profile
    # ------------------------------------------------------------------
    def get_client_for_current_user(self, client_id):
        client = (
            Client.query
            .filter(
                Client.id == client_id,
                Client.organization_id == self._require_organization_id(),
            )
            .first()
        )
        if not client:
            raise ValueError("Cliente não encontrado para a organização atual.")
        return client

    def get_importer_fiscal_profile(self, importer_id) -> ClientFiscalProfile:
        profile = (
            self.client_fiscal_profile_query_for_current_user()
            .filter(
                ClientFiscalProfile.client_id == importer_id,
                ClientFiscalProfile.is_default.is_(True),
            )
            .first()
        )
        if not profile:
            raise ValueError(
                "Perfil fiscal do importador não encontrado. "
                "Cadastre CNPJ, inscrição estadual, regime tributário e endereço fiscal antes de gerar a NF-e."
            )
        return profile

    def get_importer_fiscal_profile_or_none(self, importer_id) -> ClientFiscalProfile | None:
        return (
            self.client_fiscal_profile_query_for_current_user()
            .filter(
                ClientFiscalProfile.client_id == importer_id,
                ClientFiscalProfile.is_default.is_(True),
            )
            .first()
        )

    def create_or_update_client_fiscal_profile(self, payload: dict[str, Any]) -> ClientFiscalProfile:
        """Cria ou atualiza o perfil fiscal default de um cliente/importador.

        Espera que o schema da rota já tenha validado os campos obrigatórios.
        Mesmo assim, normaliza CNPJ, IE, CEP, UF e campos vazios.
        """
        client_id = payload.get("client_id")
        if not client_id:
            raise ValueError("client_id é obrigatório.")

        self.get_client_for_current_user(client_id)

        profile = self.get_importer_fiscal_profile_or_none(client_id)
        now = datetime.utcnow()

        if not profile:
            profile = ClientFiscalProfile(
                organization_id=self._require_organization_id(),
                client_id=client_id,
                is_default=True,
                created_at=now,
                updated_at=now,
            )
            db.session.add(profile)

        profile.legal_name = str(payload["legal_name"]).strip()
        profile.trade_name = self._empty_to_none(payload.get("trade_name"))
        profile.cnpj = self._digits(payload["cnpj"])
        profile.state_registration = self._empty_to_none(self._digits(payload.get("state_registration")))
        profile.tax_regime = str(payload["tax_regime"])

        profile.street = str(payload["street"]).strip()
        profile.number = str(payload["number"]).strip()
        profile.complement = self._empty_to_none(payload.get("complement"))
        profile.district = str(payload["district"]).strip()
        profile.city_code = self._digits(payload["city_code"])
        profile.city_name = str(payload["city_name"]).strip()
        profile.state = str(payload["state"]).strip().upper()
        profile.zip_code = self._digits(payload["zip_code"])

        profile.country_code = self._digits(payload.get("country_code") or "1058")
        profile.country_name = payload.get("country_name") or "Brasil"
        profile.phone = self._empty_to_none(self._digits(payload.get("phone")))
        profile.email = self._empty_to_none(payload.get("email"))
        profile.is_default = bool(payload.get("is_default", True))
        profile.updated_at = now

        self.validate_client_fiscal_profile(profile)
        db.session.flush()
        return profile

    def validate_client_fiscal_profile(self, profile: ClientFiscalProfile) -> None:
        errors = []
        if len(self._digits(profile.cnpj)) != 14:
            errors.append("CNPJ do perfil fiscal deve conter 14 dígitos.")
        if not profile.legal_name:
            errors.append("Razão social do perfil fiscal é obrigatória.")
        if profile.tax_regime not in {"1", "2", "3"}:
            errors.append("Regime tributário deve ser 1, 2 ou 3.")
        if not profile.street:
            errors.append("Logradouro é obrigatório.")
        if not profile.number:
            errors.append("Número do endereço é obrigatório.")
        if not profile.district:
            errors.append("Bairro é obrigatório.")
        if len(self._digits(profile.city_code)) != 7:
            errors.append("Código IBGE do município deve conter 7 dígitos.")
        if not profile.city_name:
            errors.append("Município é obrigatório.")
        if len(str(profile.state or "")) != 2:
            errors.append("UF deve conter 2 caracteres.")
        if len(self._digits(profile.zip_code)) != 8:
            errors.append("CEP deve conter 8 dígitos.")
        if errors:
            raise ValueError("Perfil fiscal inválido: " + " ".join(errors))

    # ------------------------------------------------------------------
    # Import process
    # ------------------------------------------------------------------
    def create_import_process(self, payload: dict[str, Any]) -> ImportProcess:
        now = datetime.utcnow()
        self.get_client_for_current_user(payload["importer_id"])

        process = ImportProcess(
            organization_id=self._require_organization_id(),
            importer_id=payload["importer_id"],
            reference_code=payload["reference_code"],
            duimp_number=payload.get("duimp_number"),
            duimp_version=payload.get("duimp_version"),
            source=payload.get("source") or ImportProcessSource.MANUAL.value,
            status=ImportProcessStatus.CREATED.value,
            created_by_user_id=self.user_id,
            created_at=now,
            updated_at=now,
        )
        db.session.add(process)
        db.session.flush()
        return process

    def update_import_process(self, process: ImportProcess, payload: dict[str, Any]) -> ImportProcess:
        for field in ["reference_code", "duimp_number", "duimp_version", "status", "source"]:
            if field in payload:
                setattr(process, field, payload[field])
        process.updated_at = datetime.utcnow()
        db.session.flush()
        return process

    def list_import_processes(self, params: dict[str, Any]) -> dict[str, Any]:
        query = self.import_process_query_for_current_user()

        if params.get("status"):
            query = query.filter(ImportProcess.status == params["status"])
        if params.get("source"):
            query = query.filter(ImportProcess.source == params["source"])
        if params.get("importer_id"):
            query = query.filter(ImportProcess.importer_id == params["importer_id"])
        if params.get("duimp_number"):
            query = query.filter(ImportProcess.duimp_number == params["duimp_number"])
        if params.get("q"):
            term = f"%{params['q']}%"
            query = query.filter(
                or_(
                    ImportProcess.reference_code.ilike(term),
                    ImportProcess.duimp_number.ilike(term),
                    ImportProcess.status.ilike(term),
                    ImportProcess.source.ilike(term),
                )
            )

        total = query.count()
        rows = (
            query.order_by(ImportProcess.updated_at.desc().nullslast(), ImportProcess.created_at.desc())
            .limit(params["limit"])
            .offset(params["offset"])
            .all()
        )
        return {"items": [self.build_import_process_summary(row) for row in rows], "total": total, **params}

    def build_import_process_summary(self, process: ImportProcess) -> dict[str, Any]:
        latest_draft = (
            NfeDraft.query.filter(NfeDraft.import_process_id == process.id)
            .order_by(NfeDraft.updated_at.desc().nullslast(), NfeDraft.created_at.desc())
            .first()
        )
        snapshots_count = DuimpSnapshot.query.filter(DuimpSnapshot.import_process_id == process.id).count()
        items_count = 0
        if latest_draft:
            items_count = NfeDraftItem.query.filter(NfeDraftItem.nfe_draft_id == latest_draft.id).count()

        profile_exists = self.get_importer_fiscal_profile_or_none(process.importer_id) is not None

        return {
            "id": str(process.id),
            "organization_id": str(process.organization_id),
            "importer_id": str(process.importer_id),
            "reference_code": process.reference_code,
            "duimp_number": process.duimp_number,
            "duimp_version": process.duimp_version,
            "status": process.status,
            "source": process.source,
            "has_fiscal_profile": profile_exists,
            "snapshots_count": snapshots_count,
            "latest_draft_id": str(latest_draft.id) if latest_draft else None,
            "latest_draft_status": latest_draft.status if latest_draft else None,
            "items_count": items_count,
            "created_at": self._iso(process.created_at),
            "updated_at": self._iso(process.updated_at),
        }

    # ------------------------------------------------------------------
    # Provider connections
    # ------------------------------------------------------------------
    def create_provider_connection(self, payload: dict[str, Any]) -> ExternalProviderConnection:
        now = datetime.utcnow()
        connection = ExternalProviderConnection(
            organization_id=self._require_organization_id(),
            importer_id=payload.get("importer_id"),
            provider=payload["provider"],
            environment=payload["environment"],
            auth_type=payload["auth_type"],
            status=payload.get("status") or "active",
            config_json=payload.get("config_json"),
            credentials_ref=payload.get("credentials_ref"),
            created_at=now,
            updated_at=now,
        )
        db.session.add(connection)
        db.session.flush()
        return connection

    def list_provider_connections(self, params: dict[str, Any]) -> dict[str, Any]:
        query = self.provider_connection_query_for_current_user()
        for field in ["importer_id", "provider", "environment", "status"]:
            if params.get(field):
                query = query.filter(getattr(ExternalProviderConnection, field) == params[field])

        total = query.count()
        rows = (
            query.order_by(ExternalProviderConnection.updated_at.desc())
            .limit(params["limit"])
            .offset(params["offset"])
            .all()
        )
        return {"items": rows, "total": total, "limit": params["limit"], "offset": params["offset"]}

    # ------------------------------------------------------------------
    # DUIMP snapshot
    # ------------------------------------------------------------------
    def create_manual_duimp_snapshot(self, process: ImportProcess, payload: dict[str, Any]) -> DuimpSnapshot:
        normalized = payload.get("normalized_payload") or self.normalize_duimp_payload(payload["raw_payload"])
        snapshot = self._create_duimp_snapshot(
            process=process,
            duimp_number=payload["duimp_number"],
            duimp_version=payload.get("duimp_version"),
            raw_payload=payload["raw_payload"],
            normalized_payload=normalized,
            source_provider=payload.get("source_provider") or ExternalProvider.PORTAL_UNICO.value,
        )
        process.duimp_number = payload["duimp_number"]
        process.duimp_version = payload.get("duimp_version")
        process.status = ImportProcessStatus.DUIMP_FETCHED.value
        process.updated_at = datetime.utcnow()
        db.session.flush()
        return snapshot

    # ------------------------------------------------------------------
    # NFe draft
    # ------------------------------------------------------------------
    def create_nfe_draft_from_duimp(self, process: ImportProcess, payload: dict[str, Any]) -> dict[str, Any]:
        if not process.duimp_number and not payload.get("duimp_payload"):
            raise ValueError("Processo não possui duimp_number e nenhum duimp_payload foi enviado.")

        fiscal_profile = self.get_importer_fiscal_profile(process.importer_id)

        started_at = datetime.utcnow()
        process.status = ImportProcessStatus.DUIMP_FETCHING.value
        process.updated_at = started_at
        db.session.flush()

        try:
            raw_duimp = self.duimp_gateway.fetch_duimp(
                duimp_number=process.duimp_number or payload["duimp_payload"].get("numero") or payload["duimp_payload"].get("number"),
                duimp_payload=payload.get("duimp_payload"),
            )
            finished_at = datetime.utcnow()
            self._log_external_request(
                process=process,
                provider=payload.get("source_provider") or ExternalProvider.PORTAL_UNICO.value,
                endpoint_name="duimp.fetch",
                method=HttpMethod.GET.value,
                request_payload={"duimp_number": process.duimp_number},
                response_payload=raw_duimp,
                success=True,
                status_code=200,
                started_at=started_at,
                finished_at=finished_at,
            )
        except Exception as exc:
            finished_at = datetime.utcnow()
            process.status = ImportProcessStatus.DUIMP_FETCH_FAILED.value
            process.updated_at = finished_at
            self._log_external_request(
                process=process,
                provider=payload.get("source_provider") or ExternalProvider.PORTAL_UNICO.value,
                endpoint_name="duimp.fetch",
                method=HttpMethod.GET.value,
                request_payload={"duimp_number": process.duimp_number},
                response_payload=None,
                success=False,
                status_code=None,
                error_code=exc.__class__.__name__,
                error_message=str(exc),
                started_at=started_at,
                finished_at=finished_at,
            )
            raise

        normalized = self.normalize_duimp_payload(raw_duimp)
        snapshot = self._create_duimp_snapshot(
            process=process,
            duimp_number=normalized["number"],
            duimp_version=normalized.get("version"),
            raw_payload=raw_duimp,
            normalized_payload=normalized,
            source_provider=payload.get("source_provider") or ExternalProvider.PORTAL_UNICO.value,
        )

        fiscal_payload = self.map_duimp_to_nfe_payload(
            duimp=normalized,
            process=process,
            fiscal_profile=fiscal_profile,
            environment=payload["environment"],
            series=payload["series"],
            number=payload.get("number"),
            import_purpose=payload["import_purpose"],
        )

        validation = self.validate_nfe_payload(fiscal_payload)
        now = datetime.utcnow()
        draft_status = NfeDraftStatus.READY_FOR_XML.value if validation.is_valid else NfeDraftStatus.VALIDATION_FAILED.value

        draft = NfeDraft(
            organization_id=self._require_organization_id(),
            import_process_id=process.id,
            importer_id=process.importer_id,
            duimp_snapshot_id=snapshot.id,
            model=NfeModel.NFE.value,
            purpose=NfePurpose.NORMAL.value,
            operation_type=NfeOperationType.ENTRY.value,
            environment=payload["environment"],
            series=payload["series"],
            number=payload.get("number"),
            status=draft_status,
            fiscal_payload=fiscal_payload,
            validation_errors=validation.errors or None,
            validation_warnings=validation.warnings or None,
            created_at=now,
            updated_at=now,
        )
        db.session.add(draft)
        db.session.flush()

        for item_payload in fiscal_payload["items"]:
            item = self._build_draft_item(draft=draft, item_payload=item_payload)
            db.session.add(item)

        process.duimp_number = normalized["number"]
        process.duimp_version = normalized.get("version")
        process.status = (
            ImportProcessStatus.DRAFT_READY.value
            if validation.is_valid
            else ImportProcessStatus.DRAFT_VALIDATION_FAILED.value
        )
        process.updated_at = now
        db.session.flush()

        return {"draft": draft, "snapshot": snapshot, "validation": validation.to_dict()}

    def get_nfe_draft_detail(self, draft: NfeDraft) -> dict[str, Any]:
        items = (
            NfeDraftItem.query.filter(NfeDraftItem.nfe_draft_id == draft.id)
            .order_by(NfeDraftItem.item_number.asc())
            .all()
        )
        xml_versions = (
            NfeXmlVersion.query.filter(NfeXmlVersion.nfe_draft_id == draft.id)
            .order_by(NfeXmlVersion.version_number.desc())
            .all()
        )
        return {"draft": draft, "items": items, "xml_versions": xml_versions}

    def update_draft_item(self, draft: NfeDraft, item: NfeDraftItem, payload: dict[str, Any]) -> NfeDraftItem:
        allowed_fields = [
            "product_code",
            "description",
            "ncm",
            "cfop",
            "cest",
            "commercial_unit",
            "commercial_quantity",
            "commercial_unit_value",
            "taxable_unit",
            "taxable_quantity",
            "taxable_unit_value",
            "product_value",
            "freight_value",
            "insurance_value",
            "discount_value",
            "other_value",
            "import_payload",
            "tax_payload",
        ]
        for field in allowed_fields:
            if field in payload:
                setattr(item, field, payload[field])

        item.updated_at = datetime.utcnow()
        self._refresh_draft_payload_from_items(draft)
        validation = self.validate_nfe_payload(draft.fiscal_payload)
        draft.validation_errors = validation.errors or None
        draft.validation_warnings = validation.warnings or None
        draft.status = NfeDraftStatus.READY_FOR_XML.value if validation.is_valid else NfeDraftStatus.VALIDATION_FAILED.value
        draft.updated_at = datetime.utcnow()
        db.session.flush()
        return item

    def validate_draft(self, draft: NfeDraft) -> ValidationResult:
        self._refresh_draft_payload_from_items(draft)
        validation = self.validate_nfe_payload(draft.fiscal_payload)
        draft.validation_errors = validation.errors or None
        draft.validation_warnings = validation.warnings or None
        draft.status = NfeDraftStatus.READY_FOR_XML.value if validation.is_valid else NfeDraftStatus.VALIDATION_FAILED.value
        draft.updated_at = datetime.utcnow()
        db.session.flush()
        return validation

    def generate_unsigned_xml(self, draft: NfeDraft) -> NfeXmlVersion:
        draft = self.get_nfe_draft_or_404(draft.id)

        if not draft.access_key:
            self.generate_access_key_for_draft(draft.id)
            db.session.flush()
            draft = self.get_nfe_draft_or_404(draft.id)

        validation = self.validate_draft(draft)
        if not validation.is_valid:
            raise ValueError("Rascunho fiscal inválido. Corrija os erros antes de gerar XML.")

        xml_content = self._build_unsigned_xml_preview(draft)
        latest_version = (
            NfeXmlVersion.query.filter(
                NfeXmlVersion.nfe_draft_id == draft.id,
                NfeXmlVersion.xml_type == NfeXmlType.UNSIGNED.value,
            )
            .order_by(NfeXmlVersion.version_number.desc())
            .first()
        )
        version_number = (latest_version.version_number if latest_version else 0) + 1
        row = NfeXmlVersion(
            nfe_draft_id=draft.id,
            version_number=version_number,
            xml_type=NfeXmlType.UNSIGNED.value,
            xml_content=xml_content,
            xsd_valid=None,
            xsd_errors=None,
            access_key=draft.access_key,
            generated_by_user_id=self.user_id,
            generated_at=datetime.utcnow(),
        )
        db.session.add(row)

        draft.status = NfeDraftStatus.XML_GENERATED.value
        draft.updated_at = datetime.utcnow()

        process = self.import_process_query_for_current_user().filter(ImportProcess.id == draft.import_process_id).first()
        if process:
            process.status = ImportProcessStatus.XML_GENERATED.value
            process.updated_at = datetime.utcnow()

        db.session.flush()
        return row

    # ------------------------------------------------------------------
    # Normalization / mapping / validation
    # ------------------------------------------------------------------
    def normalize_duimp_payload(self, raw_payload: dict[str, Any]) -> dict[str, Any]:
        raw_items = raw_payload.get("itens") or raw_payload.get("items") or []
        normalized_items = []

        for index, raw_item in enumerate(raw_items, start=1):
            quantity = self._decimal(raw_item.get("quantidade") or raw_item.get("quantity") or 0)
            product_value = self._decimal(
                raw_item.get("valorProduto")
                or raw_item.get("productValue")
                or raw_item.get("valor")
                or 0
            )
            unit_value = self._decimal(raw_item.get("valorUnitario") or raw_item.get("unitValue") or 0)
            if unit_value == 0 and quantity > 0 and product_value > 0:
                unit_value = product_value / quantity

            normalized_items.append(
                {
                    "number": str(raw_item.get("numeroItem") or raw_item.get("number") or index),
                    "product_code": str(raw_item.get("codigoProduto") or raw_item.get("productCode") or index),
                    "description": raw_item.get("descricao") or raw_item.get("description") or "Mercadoria importada",
                    "ncm": self._digits(raw_item.get("ncm") or raw_item.get("NCM") or ""),
                    "commercial_unit": raw_item.get("unidade") or raw_item.get("commercialUnit") or "UN",
                    "quantity": str(quantity),
                    "unit_value": str(unit_value),
                    "product_value": str(product_value),
                    "taxable_unit": raw_item.get("unidadeTributavel") or raw_item.get("taxableUnit") or raw_item.get("unidade") or "UN",
                    "taxable_quantity": str(self._decimal(raw_item.get("quantidadeTributavel") or raw_item.get("taxableQuantity") or quantity)),
                    "taxable_unit_value": str(self._decimal(raw_item.get("valorUnitarioTributavel") or raw_item.get("taxableUnitValue") or unit_value)),
                    "addition_number": raw_item.get("numeroAdicao") or raw_item.get("additionNumber"),
                    "sequence_number": raw_item.get("sequenciaAdicao") or raw_item.get("sequenceNumber"),
                    "manufacturer_code": raw_item.get("codigoFabricante") or raw_item.get("manufacturerCode"),
                    "exporter_code": raw_item.get("codigoExportador") or raw_item.get("exporterCode"),
                    "drawback_number": raw_item.get("numeroDrawback") or raw_item.get("drawbackNumber"),
                    "freight_value": str(self._decimal(raw_item.get("valorFrete") or raw_item.get("freightValue") or 0)),
                    "insurance_value": str(self._decimal(raw_item.get("valorSeguro") or raw_item.get("insuranceValue") or 0)),
                    "discount_value": str(self._decimal(raw_item.get("valorDesconto") or raw_item.get("discountValue") or 0)),
                    "other_value": str(self._decimal(raw_item.get("valorOutrasDespesas") or raw_item.get("otherValue") or 0)),
                    "taxes": raw_item.get("tributos") or raw_item.get("taxes") or {},
                    "raw": raw_item,
                }
            )

        return {
            "number": raw_payload.get("numero") or raw_payload.get("number"),
            "version": raw_payload.get("versao") or raw_payload.get("version"),
            "registration_date": raw_payload.get("dataRegistro") or raw_payload.get("registrationDate"),
            "clearance_location": raw_payload.get("localDesembaraco") or raw_payload.get("clearanceLocation"),
            "clearance_state": raw_payload.get("ufDesembaraco") or raw_payload.get("clearanceState"),
            "clearance_date": raw_payload.get("dataDesembaraco") or raw_payload.get("clearanceDate"),
            "transport_mode_code": raw_payload.get("viaTransporteCodigo") or raw_payload.get("transportModeCode"),
            "afrmm_value": str(self._decimal(raw_payload.get("valorAfrmm") or raw_payload.get("afrmmValue") or 0)),
            "intermediation_type": raw_payload.get("tipoIntermedio") or raw_payload.get("intermediationType") or "1",
            "exporter_code": raw_payload.get("codigoExportador") or raw_payload.get("exporterCode"),
            "items": normalized_items,
            "raw": raw_payload,
        }

    def map_duimp_to_nfe_payload(
        self,
        *,
        duimp: dict[str, Any],
        process: ImportProcess,
        fiscal_profile: ClientFiscalProfile,
        environment: str,
        series: str,
        number: int | None,
        import_purpose: str,
    ) -> dict[str, Any]:
        items = self.map_duimp_items_to_nfe_items(
            duimp=duimp,
            import_purpose=import_purpose,
        )
        totals = self.calculate_nfe_totals(items)
        party = self.build_fiscal_party_from_profile(fiscal_profile)

        return {
            "document": {
                "model": NfeModel.NFE.value,
                "purpose": NfePurpose.NORMAL.value,
                "operation_type": NfeOperationType.ENTRY.value,
                "environment": environment,
                "series": series,
                "number": number,
                "operation_nature": "Importação de mercadoria",
                "import_purpose": import_purpose,
                "currency": "BRL",
            },
            "import_process": {
                "id": str(process.id),
                "reference_code": process.reference_code,
            },
            "duimp": {
                "number": duimp["number"],
                "version": duimp.get("version"),
                "registration_date": duimp.get("registration_date"),
                "clearance_location": duimp.get("clearance_location"),
                "clearance_state": duimp.get("clearance_state"),
                "clearance_date": duimp.get("clearance_date"),
                "transport_mode_code": duimp.get("transport_mode_code"),
                "afrmm_value": duimp.get("afrmm_value", "0"),
                "intermediation_type": duimp.get("intermediation_type") or "1",
                "exporter_code": duimp.get("exporter_code"),
            },
            "issuer": party,
            "recipient": party,
            "items": items,
            "totals": totals,
            "additional_info": {
                "complementary": f"NF-e de entrada de importação gerada com base na DUIMP {duimp['number']}.",
            },
            "source": {
                "import_process_id": str(process.id),
                "duimp_source": "DUIMP",
                "fiscal_profile_id": str(fiscal_profile.id),
            },
        }

    def build_fiscal_party_from_profile(self, profile: ClientFiscalProfile) -> dict[str, Any]:
        return {
            "client_id": str(profile.client_id),
            "fiscal_profile_id": str(profile.id),
            "cnpj": self._digits(profile.cnpj),
            "legal_name": profile.legal_name,
            "trade_name": profile.trade_name,
            "state_registration": self._digits(profile.state_registration),
            "tax_regime": profile.tax_regime,
            "address": {
                "street": profile.street,
                "number": profile.number,
                "complement": profile.complement,
                "district": profile.district,
                "city_code": self._digits(profile.city_code),
                "city_name": profile.city_name,
                "state": profile.state,
                "zip_code": self._digits(profile.zip_code),
                "country_code": profile.country_code or "1058",
                "country_name": profile.country_name or "Brasil",
            },
            "contact": {
                "phone": self._digits(profile.phone),
                "email": profile.email,
            },
        }

    def map_duimp_items_to_nfe_items(self, *, duimp: dict[str, Any], import_purpose: str) -> list[dict[str, Any]]:
        mapped_items = []
        cfop = self._resolve_cfop(import_purpose)

        for index, item in enumerate(duimp.get("items", []), start=1):
            product_value = self._decimal(item.get("product_value"))
            quantity = self._decimal(item.get("quantity"))
            unit_value = self._decimal(item.get("unit_value"))
            if unit_value == 0 and quantity > 0:
                unit_value = product_value / quantity

            mapped_items.append(
                {
                    "item_number": index,
                    "duimp_item_number": item["number"],
                    "product_code": item["product_code"],
                    "description": item["description"],
                    "ncm": item["ncm"],
                    "cfop": cfop,
                    "cest": item.get("cest"),
                    "commercial_unit": item["commercial_unit"],
                    "commercial_quantity": str(quantity),
                    "commercial_unit_value": str(unit_value),
                    "taxable_unit": item["taxable_unit"],
                    "taxable_quantity": item["taxable_quantity"],
                    "taxable_unit_value": item["taxable_unit_value"],
                    "product_value": str(product_value),
                    "freight_value": item.get("freight_value", "0"),
                    "insurance_value": item.get("insurance_value", "0"),
                    "discount_value": item.get("discount_value", "0"),
                    "other_value": item.get("other_value", "0"),
                    "import_payload": {
                        "duimp_number": duimp["number"],
                        "duimp_version": duimp.get("version"),
                        "registration_date": duimp.get("registration_date"),
                        "duimp_item_number": item["number"],
                        "addition_number": item.get("addition_number"),
                        "sequence_number": item.get("sequence_number"),
                        "manufacturer_code": item.get("manufacturer_code"),
                        "exporter_code": item.get("exporter_code") or duimp.get("exporter_code"),
                        "drawback_number": item.get("drawback_number"),
                    },
                    "tax_payload": item.get("taxes") or {},
                    "raw_source_payload": item.get("raw"),
                }
            )
        return mapped_items

    def calculate_nfe_totals(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        products_value = Decimal("0")
        freight_value = Decimal("0")
        insurance_value = Decimal("0")
        discount_value = Decimal("0")
        other_value = Decimal("0")
        ii_value = Decimal("0")
        ipi_value = Decimal("0")
        pis_value = Decimal("0")
        cofins_value = Decimal("0")
        icms_value = Decimal("0")

        for item in items:
            products_value += self._decimal(item.get("product_value"))
            freight_value += self._decimal(item.get("freight_value"))
            insurance_value += self._decimal(item.get("insurance_value"))
            discount_value += self._decimal(item.get("discount_value"))
            other_value += self._decimal(item.get("other_value"))

            taxes = item.get("tax_payload") or {}
            ii_value += self._decimal((taxes.get("ii") or {}).get("value"))
            ipi_value += self._decimal((taxes.get("ipi") or {}).get("value"))
            pis_value += self._decimal((taxes.get("pis") or {}).get("value"))
            cofins_value += self._decimal((taxes.get("cofins") or {}).get("value"))
            icms_value += self._decimal((taxes.get("icms") or {}).get("value"))

        invoice_value = (
            products_value
            + freight_value
            + insurance_value
            + other_value
            + ii_value
            + ipi_value
            + pis_value
            + cofins_value
            + icms_value
            - discount_value
        )

        return {
            "products_value": str(products_value),
            "freight_value": str(freight_value),
            "insurance_value": str(insurance_value),
            "discount_value": str(discount_value),
            "other_value": str(other_value),
            "ii_value": str(ii_value),
            "ipi_value": str(ipi_value),
            "pis_value": str(pis_value),
            "cofins_value": str(cofins_value),
            "icms_value": str(icms_value),
            "invoice_value": str(invoice_value),
        }

    def validate_nfe_payload(self, payload: dict[str, Any]) -> ValidationResult:
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        document = payload.get("document") or {}
        if document.get("model") != NfeModel.NFE.value:
            errors.append({"field": "document.model", "message": "Modelo da NF-e deve ser 55."})
        if document.get("operation_type") != NfeOperationType.ENTRY.value:
            errors.append({"field": "document.operation_type", "message": "NF-e de importação deve ser operação de entrada."})
        if document.get("environment") not in FiscalEnvironment.values():
            errors.append({"field": "document.environment", "message": "Ambiente fiscal inválido."})
        if not document.get("series"):
            errors.append({"field": "document.series", "message": "Série da NF-e é obrigatória."})

        duimp = payload.get("duimp") or {}
        if not duimp.get("number"):
            errors.append({"field": "duimp.number", "message": "Número da DUIMP é obrigatório."})

        self._validate_fiscal_party(payload.get("issuer") or {}, errors, "issuer")
        self._validate_fiscal_party(payload.get("recipient") or {}, errors, "recipient")

        items = payload.get("items") or []
        if not items:
            errors.append({"field": "items", "message": "A NF-e precisa ter ao menos um item."})

        for index, item in enumerate(items, start=1):
            prefix = f"items[{index}]"
            if not item.get("description"):
                errors.append({"field": f"{prefix}.description", "message": "Descrição do item é obrigatória."})
            if len(self._digits(item.get("ncm"))) != 8:
                errors.append({"field": f"{prefix}.ncm", "message": "NCM deve conter 8 dígitos."})
            if not str(item.get("cfop", "")).startswith("3"):
                errors.append({"field": f"{prefix}.cfop", "message": "CFOP de importação deve iniciar com 3."})
            if self._decimal(item.get("commercial_quantity")) <= 0:
                errors.append({"field": f"{prefix}.commercial_quantity", "message": "Quantidade comercial deve ser maior que zero."})
            if self._decimal(item.get("product_value")) <= 0:
                errors.append({"field": f"{prefix}.product_value", "message": "Valor do produto deve ser maior que zero."})
            if not item.get("import_payload"):
                errors.append({"field": f"{prefix}.import_payload", "message": "Dados de importação são obrigatórios."})
            if not item.get("tax_payload"):
                warnings.append({"field": f"{prefix}.tax_payload", "message": "Tributos ainda não foram preenchidos."})

        warnings.append(
            {
                "field": "tax_rules",
                "message": "Revisar CST/CSOSN, ICMS, II, IPI, PIS e COFINS antes da autorização da NF-e.",
            }
        )
        return ValidationResult(errors=errors, warnings=warnings)

    def _validate_fiscal_party(self, party: dict[str, Any], errors: list[dict[str, Any]], prefix: str) -> None:
        if len(self._digits(party.get("cnpj"))) != 14:
            errors.append({"field": f"{prefix}.cnpj", "message": "CNPJ deve conter 14 dígitos."})
        if not party.get("legal_name"):
            errors.append({"field": f"{prefix}.legal_name", "message": "Razão social é obrigatória."})
        if party.get("tax_regime") not in {"1", "2", "3"}:
            errors.append({"field": f"{prefix}.tax_regime", "message": "Regime tributário deve ser 1, 2 ou 3."})

        address = party.get("address") or {}
        required_fields = {
            "street": "Logradouro é obrigatório.",
            "number": "Número do endereço é obrigatório.",
            "district": "Bairro é obrigatório.",
            "city_code": "Código IBGE do município é obrigatório.",
            "city_name": "Município é obrigatório.",
            "state": "UF é obrigatória.",
            "zip_code": "CEP é obrigatório.",
        }
        for field, message in required_fields.items():
            if not address.get(field):
                errors.append({"field": f"{prefix}.address.{field}", "message": message})

        if address.get("city_code") and len(self._digits(address.get("city_code"))) != 7:
            errors.append({"field": f"{prefix}.address.city_code", "message": "Código IBGE deve conter 7 dígitos."})
        if address.get("zip_code") and len(self._digits(address.get("zip_code"))) != 8:
            errors.append({"field": f"{prefix}.address.zip_code", "message": "CEP deve conter 8 dígitos."})
        if address.get("state") and len(str(address.get("state"))) != 2:
            errors.append({"field": f"{prefix}.address.state", "message": "UF deve conter 2 caracteres."})

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------
    def _create_duimp_snapshot(
        self,
        *,
        process: ImportProcess,
        duimp_number: str,
        duimp_version: str | None,
        raw_payload: dict[str, Any],
        normalized_payload: dict[str, Any],
        source_provider: str,
    ) -> DuimpSnapshot:
        now = datetime.utcnow()
        snapshot = DuimpSnapshot(
            organization_id=self._require_organization_id(),
            import_process_id=process.id,
            duimp_number=duimp_number,
            duimp_version=duimp_version,
            raw_payload=raw_payload,
            normalized_payload=normalized_payload,
            source_provider=source_provider,
            fetched_at=now,
            checksum=self._checksum(raw_payload),
            created_at=now,
        )
        db.session.add(snapshot)
        db.session.flush()
        return snapshot

    def _build_draft_item(self, *, draft: NfeDraft, item_payload: dict[str, Any]) -> NfeDraftItem:
        now = datetime.utcnow()
        return NfeDraftItem(
            nfe_draft_id=draft.id,
            item_number=item_payload["item_number"],
            duimp_item_number=item_payload.get("duimp_item_number"),
            product_code=item_payload["product_code"],
            description=item_payload["description"],
            ncm=item_payload["ncm"],
            cfop=item_payload["cfop"],
            cest=item_payload.get("cest"),
            commercial_unit=item_payload["commercial_unit"],
            commercial_quantity=self._decimal(item_payload["commercial_quantity"]),
            commercial_unit_value=self._decimal(item_payload["commercial_unit_value"]),
            taxable_unit=item_payload["taxable_unit"],
            taxable_quantity=self._decimal(item_payload["taxable_quantity"]),
            taxable_unit_value=self._decimal(item_payload["taxable_unit_value"]),
            product_value=self._decimal(item_payload["product_value"]),
            freight_value=self._decimal(item_payload.get("freight_value", 0)),
            insurance_value=self._decimal(item_payload.get("insurance_value", 0)),
            discount_value=self._decimal(item_payload.get("discount_value", 0)),
            other_value=self._decimal(item_payload.get("other_value", 0)),
            import_payload=item_payload.get("import_payload"),
            tax_payload=item_payload.get("tax_payload"),
            raw_source_payload=item_payload.get("raw_source_payload"),
            created_at=now,
            updated_at=now,
        )

    def _refresh_draft_payload_from_items(self, draft: NfeDraft) -> None:
        rows = (
            NfeDraftItem.query
            .filter(NfeDraftItem.nfe_draft_id == draft.id)
            .order_by(NfeDraftItem.item_number.asc())
            .all()
        )
        payload = dict(draft.fiscal_payload or {})
        payload["items"] = [self._item_to_payload(row) for row in rows]
        payload["totals"] = self.calculate_nfe_totals(payload["items"])
        draft.fiscal_payload = payload

    def _item_to_payload(self, item: NfeDraftItem) -> dict[str, Any]:
        return {
            "item_number": item.item_number,
            "duimp_item_number": item.duimp_item_number,
            "product_code": item.product_code,
            "description": item.description,
            "ncm": item.ncm,
            "cfop": item.cfop,
            "cest": item.cest,
            "commercial_unit": item.commercial_unit,
            "commercial_quantity": str(item.commercial_quantity),
            "commercial_unit_value": str(item.commercial_unit_value),
            "taxable_unit": item.taxable_unit,
            "taxable_quantity": str(item.taxable_quantity),
            "taxable_unit_value": str(item.taxable_unit_value),
            "product_value": str(item.product_value),
            "freight_value": str(item.freight_value),
            "insurance_value": str(item.insurance_value),
            "discount_value": str(item.discount_value),
            "other_value": str(item.other_value),
            "import_payload": item.import_payload,
            "tax_payload": item.tax_payload,
            "raw_source_payload": item.raw_source_payload,
        }

    def _build_unsigned_xml_preview(self, draft: NfeDraft) -> str:
        payload = draft.fiscal_payload
        document = payload["document"]
        duimp = payload["duimp"]
        issuer = payload.get("issuer") or {}
        recipient = payload.get("recipient") or {}
        items = payload.get("items") or []

        det_xml = []
        for item in items:
            det_xml.append(
                f"""
    <det nItem=\"{item['item_number']}\">
      <prod>
        <cProd>{escape(str(item['product_code']))}</cProd>
        <xProd>{escape(str(item['description']))}</xProd>
        <NCM>{escape(str(item['ncm']))}</NCM>
        <CFOP>{escape(str(item['cfop']))}</CFOP>
        <uCom>{escape(str(item['commercial_unit']))}</uCom>
        <qCom>{item['commercial_quantity']}</qCom>
        <vUnCom>{item['commercial_unit_value']}</vUnCom>
        <vProd>{item['product_value']}</vProd>
        <DI>
          <nDI>{escape(str(duimp.get('number') or ''))}</nDI>
          <dDI>{escape(str(duimp.get('registration_date') or ''))}</dDI>
          <xLocDesemb>{escape(str(duimp.get('clearance_location') or ''))}</xLocDesemb>
          <UFDesemb>{escape(str(duimp.get('clearance_state') or ''))}</UFDesemb>
          <dDesemb>{escape(str(duimp.get('clearance_date') or ''))}</dDesemb>
        </DI>
      </prod>
      <imposto />
    </det>""".strip()
            )

        return f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<NFe xmlns=\"http://www.portalfiscal.inf.br/nfe\">
  <infNFe versao=\"4.00\">
    <ide>
      <natOp>{escape(str(document.get('operation_nature') or 'Importação de mercadoria'))}</natOp>
      <mod>55</mod>
      <serie>{escape(str(document.get('series') or ''))}</serie>
      <nNF>{escape(str(document.get('number') or ''))}</nNF>
      <tpNF>0</tpNF>
      <idDest>3</idDest>
      <tpAmb>{'1' if document.get('environment') == FiscalEnvironment.PRODUCTION.value else '2'}</tpAmb>
    </ide>
    <emit>
      <CNPJ>{escape(str(issuer.get('cnpj') or ''))}</CNPJ>
      <xNome>{escape(str(issuer.get('legal_name') or ''))}</xNome>
      <IE>{escape(str(issuer.get('state_registration') or ''))}</IE>
      <CRT>{escape(str(issuer.get('tax_regime') or ''))}</CRT>
    </emit>
    <dest>
      <CNPJ>{escape(str(recipient.get('cnpj') or ''))}</CNPJ>
      <xNome>{escape(str(recipient.get('legal_name') or ''))}</xNome>
      <indIEDest>1</indIEDest>
      <IE>{escape(str(recipient.get('state_registration') or ''))}</IE>
    </dest>
    {chr(10).join(det_xml)}
    <total>
      <ICMSTot>
        <vProd>{payload.get('totals', {}).get('products_value', '0.00')}</vProd>
        <vFrete>{payload.get('totals', {}).get('freight_value', '0.00')}</vFrete>
        <vSeg>{payload.get('totals', {}).get('insurance_value', '0.00')}</vSeg>
        <vDesc>{payload.get('totals', {}).get('discount_value', '0.00')}</vDesc>
        <vII>{payload.get('totals', {}).get('ii_value', '0.00')}</vII>
        <vIPI>{payload.get('totals', {}).get('ipi_value', '0.00')}</vIPI>
        <vPIS>{payload.get('totals', {}).get('pis_value', '0.00')}</vPIS>
        <vCOFINS>{payload.get('totals', {}).get('cofins_value', '0.00')}</vCOFINS>
        <vOutro>{payload.get('totals', {}).get('other_value', '0.00')}</vOutro>
        <vNF>{payload.get('totals', {}).get('invoice_value', '0.00')}</vNF>
      </ICMSTot>
    </total>
    <infAdic>
      <infCpl>{escape(str((payload.get('additional_info') or {}).get('complementary') or ''))}</infCpl>
    </infAdic>
  </infNFe>
</NFe>"""

    def _log_external_request(
        self,
        *,
        process: ImportProcess,
        provider: str,
        endpoint_name: str,
        method: str,
        request_payload: dict[str, Any] | None,
        response_payload: dict[str, Any] | None,
        success: bool,
        status_code: int | None,
        started_at: datetime,
        finished_at: datetime,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> ExternalApiRequestLog:
        row = ExternalApiRequestLog(
            organization_id=self._require_organization_id(),
            import_process_id=process.id,
            provider=provider,
            endpoint_name=endpoint_name,
            method=method,
            request_payload=request_payload,
            response_payload=response_payload,
            status_code=status_code,
            success=success,
            error_code=error_code,
            error_message=error_message,
            started_at=started_at,
            finished_at=finished_at,
        )
        db.session.add(row)
        db.session.flush()
        return row

    def _resolve_cfop(self, import_purpose: str) -> str:
        mapping = {
            ImportPurpose.RESALE.value: "3102",
            ImportPurpose.INDUSTRIALIZATION.value: "3101",
            ImportPurpose.FIXED_ASSET.value: "3127",
            ImportPurpose.USE_CONSUMPTION.value: "3556",
            # caso você adicione esse enum depois:
            "service_use": "3126",
        }
        if import_purpose not in mapping:
            raise ValueError("Finalidade de importação inválida para definição do CFOP.")
        return mapping[import_purpose]

    def _require_organization_id(self):
        if not self.organization_id:
            raise ValueError("Usuário atual não possui organization_id.")
        return self.organization_id

    @staticmethod
    def _checksum(payload: dict[str, Any]) -> str:
        content = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        try:
            return Decimal(str(value or "0"))
        except (InvalidOperation, ValueError):
            return Decimal("0")

    @staticmethod
    def _digits(value: Any) -> str:
        return "".join(ch for ch in str(value or "") if ch.isdigit())

    @staticmethod
    def _empty_to_none(value: Any) -> str | None:
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    @staticmethod
    def _iso(value: datetime | None) -> str | None:
        return value.isoformat() + "Z" if value else None
