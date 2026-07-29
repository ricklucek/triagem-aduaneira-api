from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import or_

from ..extensions import db
from ..integrations.portal_unico import (
    DefaultPortalCredentialResolver,
    PortalUnicoDuimpGateway,
    PortalUnicoIntegrationError,
)
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
from app.services.duimp_normalizer import DuimpNormalizer
from app.services.import_tax_calculator import ImportTaxCalculator
from app.services.nfe_xml_builder import NfeXmlBuilder
from app.services.nfe_xsd_validator import (
    NfeXsdValidationResult,
    NfeXsdValidator,
)


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

    def fetch_duimp(
        self,
        *,
        duimp_number: str,
        duimp_payload: dict[str, Any] | None = None,
        enrich_catalog: bool = True,
    ) -> dict[str, Any]:
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
    def __init__(
        self,
        current_user,
        duimp_gateway: Any | None = None,
        credential_resolver: Any | None = None,
        xsd_validator: NfeXsdValidator | None = None,
    ):
        self.current_user = current_user
        self.organization_id = getattr(current_user, "organization_id", None)
        self.user_id = getattr(current_user, "id", None)
        self.duimp_gateway = duimp_gateway
        self.credential_resolver = (
            credential_resolver or DefaultPortalCredentialResolver()
        )
        self.duimp_normalizer = DuimpNormalizer()
        self.tax_calculator = ImportTaxCalculator()
        self.xml_builder = NfeXmlBuilder()
        self.xsd_validator = xsd_validator or NfeXsdValidator()

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

        validation_result = self.validate_nfe_payload(draft.fiscal_payload)
        validation = validation_result.to_dict()

        if not validation["valid"]:
            draft.status = "validation_failed"
            draft.validation_errors = validation["errors"]
            draft.validation_warnings = validation["warnings"]
            draft.updated_at = datetime.now()

            raise ValueError(
                "Rascunho fiscal inválido. Corrija os erros antes de gerar a chave de acesso."
            )

        now = datetime.now(ZoneInfo("America/Sao_Paulo")).replace(microsecond=0)

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

        fiscal_payload = deepcopy(draft.fiscal_payload or {})
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

    def fetch_duimp_for_process(
        self, process: ImportProcess, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if not process.duimp_number and not payload.get("duimp_payload"):
            raise ValueError(
                "Processo não possui duimp_number e nenhum duimp_payload foi enviado."
            )

        provider = payload.get("source_provider") or ExternalProvider.PORTAL_UNICO.value
        gateway = self._duimp_gateway_for(process=process, payload=payload)
        started_at = datetime.utcnow()
        process.status = ImportProcessStatus.DUIMP_FETCHING.value
        process.updated_at = started_at
        db.session.flush()

        manual_payload = payload.get("duimp_payload")
        duimp_number = process.duimp_number
        if not duimp_number and manual_payload:
            duimp_number = manual_payload.get("numero") or manual_payload.get("number")

        try:
            raw_duimp = gateway.fetch_duimp(
                duimp_number=duimp_number,
                duimp_payload=manual_payload,
                enrich_catalog=payload.get("enrich_catalog", True),
            )
            finished_at = datetime.utcnow()
            self._log_external_request(
                process=process,
                provider=provider,
                endpoint_name="duimp.fetch",
                method=HttpMethod.GET.value,
                request_payload={
                    "duimp_number": duimp_number,
                    "enrich_catalog": payload.get("enrich_catalog", True),
                },
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
                provider=provider,
                endpoint_name="duimp.fetch",
                method=HttpMethod.GET.value,
                request_payload={"duimp_number": duimp_number},
                response_payload=None,
                success=False,
                status_code=getattr(exc, "status_code", None),
                error_code=getattr(exc, "error_code", None)
                or exc.__class__.__name__,
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
            source_provider=provider,
        )
        process.duimp_number = normalized["number"]
        process.duimp_version = normalized.get("version")
        process.status = ImportProcessStatus.DUIMP_FETCHED.value
        process.updated_at = datetime.utcnow()
        db.session.flush()
        return {"snapshot": snapshot, "normalized": normalized}

    def _duimp_gateway_for(
        self, *, process: ImportProcess, payload: dict[str, Any]
    ) -> Any:
        if self.duimp_gateway is not None:
            return self.duimp_gateway
        if payload.get("duimp_payload") is not None:
            return MockDuimpGateway()

        provider = payload.get("source_provider") or ExternalProvider.PORTAL_UNICO.value
        if provider != ExternalProvider.PORTAL_UNICO.value:
            raise ValueError(
                f"Não existe gateway configurado para o provider {provider}."
            )

        environment = payload.get("provider_environment") or payload.get("environment")
        if environment not in FiscalEnvironment.values():
            raise ValueError("Ambiente do provider é obrigatório para consultar a DUIMP.")

        connection = self._find_provider_connection(
            process=process,
            provider=provider,
            environment=environment,
        )
        config = connection.config_json or {}
        role_type = config.get("role_type") or "IMPEXP"
        credentials = self.credential_resolver.resolve(
            connection.credentials_ref,
            role_type=role_type,
        )
        return PortalUnicoDuimpGateway(
            credentials=credentials,
            environment=environment,
            base_url=config.get("base_url"),
            timeout_seconds=float(config.get("timeout_seconds") or 30),
        )

    def _find_provider_connection(
        self,
        *,
        process: ImportProcess,
        provider: str,
        environment: str,
    ) -> ExternalProviderConnection:
        base_query = self.provider_connection_query_for_current_user().filter(
            ExternalProviderConnection.provider == provider,
            ExternalProviderConnection.environment == environment,
            ExternalProviderConnection.status == "active",
        )
        connection = base_query.filter(
            ExternalProviderConnection.importer_id == process.importer_id
        ).first()
        if connection is None:
            connection = base_query.filter(
                ExternalProviderConnection.importer_id.is_(None)
            ).first()
        if connection is None:
            raise PortalUnicoIntegrationError(
                "Conexão ativa com o Portal Único não configurada para o cliente e ambiente."
            )
        if not connection.credentials_ref:
            raise PortalUnicoIntegrationError(
                "A conexão com o Portal Único não possui credentials_ref."
            )
        return connection

    # ------------------------------------------------------------------
    # NFe draft
    # ------------------------------------------------------------------
    def create_nfe_draft_from_duimp(self, process: ImportProcess, payload: dict[str, Any]) -> dict[str, Any]:
        fiscal_profile = self.get_importer_fiscal_profile(process.importer_id)
        snapshot_id = payload.get("duimp_snapshot_id")
        if snapshot_id:
            snapshot = (
                self.snapshot_query_for_current_user()
                .filter(
                    DuimpSnapshot.id == snapshot_id,
                    DuimpSnapshot.import_process_id == process.id,
                )
                .first()
            )
            if snapshot is None:
                raise ValueError("Snapshot da DUIMP não encontrado para este processo.")
            normalized = snapshot.normalized_payload or self.normalize_duimp_payload(
                snapshot.raw_payload
            )
        else:
            fetch_result = self.fetch_duimp_for_process(process, payload)
            normalized = fetch_result["normalized"]
            snapshot = fetch_result["snapshot"]

        fiscal_payload = self.map_duimp_to_nfe_payload(
            duimp=normalized,
            process=process,
            fiscal_profile=fiscal_profile,
            environment=payload["environment"],
            series=payload["series"],
            number=payload.get("number"),
            import_purpose=payload["import_purpose"],
            tax_configuration=payload["tax_configuration"],
            additional_costs=payload.get("additional_costs"),
            foreign_supplier=payload.get("foreign_supplier"),
            duimp_overrides=payload.get("duimp_overrides"),
            transport=payload.get("transport"),
            payment=payload.get("payment"),
            additional_info=payload.get("additional_info"),
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

        xml_content = self.xml_builder.build(
            draft.fiscal_payload,
            access_key=draft.access_key,
        )
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

    def validate_xml_version(
        self,
        draft: NfeDraft,
        xml_version: NfeXmlVersion,
    ) -> NfeXsdValidationResult:
        if xml_version.nfe_draft_id != draft.id:
            raise ValueError("Versão XML não pertence ao rascunho informado.")

        xml_type = getattr(xml_version.xml_type, "value", xml_version.xml_type)
        xml_type = str(xml_type).lower()
        if xml_type not in {
            NfeXmlType.UNSIGNED.value,
            NfeXmlType.SIGNED.value,
        }:
            raise ValueError(
                "A validação XSD desta etapa suporta somente XML de NF-e "
                "não assinado ou assinado."
            )

        result = self.xsd_validator.validate(
            xml_version.xml_content,
            allow_unsigned=xml_type == NfeXmlType.UNSIGNED.value,
        )
        xml_version.xsd_valid = result.is_valid
        xml_version.xsd_errors = result.errors

        latest_version = (
            NfeXmlVersion.query.filter(
                NfeXmlVersion.nfe_draft_id == draft.id,
                NfeXmlVersion.xml_type == xml_type,
            )
            .order_by(NfeXmlVersion.version_number.desc())
            .first()
        )
        if latest_version and latest_version.id == xml_version.id:
            process = (
                self.import_process_query_for_current_user()
                .filter(ImportProcess.id == draft.import_process_id)
                .first()
            )
            if process:
                process.status = (
                    ImportProcessStatus.XML_VALIDATED.value
                    if result.is_valid
                    else ImportProcessStatus.XML_VALIDATION_FAILED.value
                )
                process.updated_at = datetime.utcnow()

        db.session.flush()
        return result

    # ------------------------------------------------------------------
    # Normalization / mapping / validation
    # ------------------------------------------------------------------
    def normalize_duimp_payload(self, raw_payload: dict[str, Any]) -> dict[str, Any]:
        return self.duimp_normalizer.normalize(raw_payload)

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
        tax_configuration: dict[str, Any],
        additional_costs: dict[str, Any] | None = None,
        foreign_supplier: dict[str, Any] | None = None,
        duimp_overrides: dict[str, Any] | None = None,
        transport: dict[str, Any] | None = None,
        payment: dict[str, Any] | None = None,
        additional_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved_additional_costs = self.resolve_additional_costs(
            duimp=duimp,
            additional_costs=additional_costs,
        )
        items = self.map_duimp_items_to_nfe_items(
            duimp=duimp,
            import_purpose=import_purpose,
        )
        items, totals = self.tax_calculator.calculate(
            items,
            configuration=tax_configuration,
            additional_costs=resolved_additional_costs,
        )
        reconciliation = self.tax_calculator.reconcile(
            items,
            totals,
            expected_tax_totals=duimp.get("tax_totals"),
            expected_additional_costs=resolved_additional_costs,
        )
        issuer = self.build_fiscal_party_from_profile(fiscal_profile)
        recipient = self.build_foreign_party_from_duimp(
            duimp,
            override=foreign_supplier,
        )
        duimp_data = {
            "number": duimp["number"],
            "api_number": duimp.get("api_number"),
            "version": duimp.get("version"),
            "registration_date": duimp.get("registration_date"),
            "clearance_location": duimp.get("clearance_location"),
            "clearance_state": duimp.get("clearance_state"),
            "clearance_date": duimp.get("clearance_date"),
            "transport_mode_code": duimp.get("transport_mode_code"),
            "afrmm_value": duimp.get("afrmm_value", "0"),
            "intermediation_type": duimp.get("intermediation_type") or "1",
            "exporter_code": duimp.get("exporter_code"),
            "import_modality": duimp.get("import_modality"),
            "third_party_tax_id": duimp.get("third_party_tax_id"),
        }
        duimp_data.update(duimp_overrides or {})

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
                "import_modality": duimp.get("import_modality"),
                "currency": "BRL",
            },
            "import_process": {
                "id": str(process.id),
                "reference_code": process.reference_code,
            },
            "duimp": duimp_data,
            "issuer": issuer,
            "recipient": recipient,
            "items": items,
            "totals": totals,
            "additional_costs": resolved_additional_costs,
            "reconciliation": reconciliation,
            "transport": transport or {"freight_mode": "9"},
            "payment": payment or {"method": "90", "value": "0.00"},
            "additional_info": {
                "complementary": f"NF-e de entrada de importação gerada com base na DUIMP {duimp['number']}.",
                **(additional_info or {}),
            },
            "source": {
                "import_process_id": str(process.id),
                "duimp_source": "DUIMP",
                "fiscal_profile_id": str(fiscal_profile.id),
            },
        }

    def resolve_additional_costs(
        self,
        *,
        duimp: dict[str, Any],
        additional_costs: dict[str, Any] | None,
    ) -> dict[str, Any]:
        resolved = dict(additional_costs or {})
        defaults = {
            "afrmm": duimp.get("afrmm_value") or "0",
            "siscomex_fee": self._duimp_siscomex_fee(duimp),
            "thc": "0",
            "other": "0",
        }
        for name, default in defaults.items():
            if resolved.get(name) in (None, ""):
                resolved[name] = default
        return resolved

    @staticmethod
    def _duimp_siscomex_fee(duimp: dict[str, Any]) -> Any:
        tax_totals = duimp.get("tax_totals") or {}
        for name in (
            "taxa_utilizacao",
            "taxa_utilizacao_siscomex",
            "taxa_siscomex",
        ):
            tax = tax_totals.get(name)
            if isinstance(tax, dict):
                value = tax.get("value")
            else:
                value = tax
            if value not in (None, ""):
                return value
        return "0"

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

    def build_foreign_party_from_duimp(
        self,
        duimp: dict[str, Any],
        *,
        override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        supplier = dict(duimp.get("foreign_supplier") or {})
        supplier.update(override or {})
        address = supplier.get("address") or {}
        if isinstance(address, str):
            address = {"street": address}

        country = supplier.get("country") or {}
        return {
            "party_type": "foreign",
            "foreign_id": supplier.get("foreign_id")
            or supplier.get("foreign_tax_id"),
            "legal_name": supplier.get("legal_name") or supplier.get("name"),
            "ind_ie_dest": "9",
            "address": {
                "street": address.get("street")
                or address.get("logradouro")
                or "EXTERIOR",
                "number": address.get("number") or address.get("numero") or "0",
                "complement": address.get("complement")
                or address.get("complemento"),
                "district": address.get("district")
                or address.get("bairro")
                or "EXTERIOR",
                "city_code": "9999999",
                "city_name": address.get("city_name")
                or address.get("municipio")
                or "EXTERIOR",
                "state": "EX",
                "zip_code": None,
                "country_code": supplier.get("country_code")
                or country.get("code")
                or country.get("codigo"),
                "country_name": supplier.get("country_name")
                or supplier.get("country_name_pt")
                or country.get("name")
                or country.get("descricao"),
                "country_iso_alpha_2": supplier.get("country_iso_alpha_2"),
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
                    "customs_value": item.get("customs_value")
                    or str(product_value),
                    "net_weight": item.get("net_weight", "0"),
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
                    "tax_classification_code": item.get("tax_classification_code"),
                    "raw_source_payload": item.get("raw"),
                }
            )
        return mapped_items

    def calculate_nfe_totals(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        return self.tax_calculator.calculate_totals(items)

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
        for field, message in {
            "registration_date": "Data de registro da DUIMP é obrigatória.",
            "clearance_location": "Local de desembaraço é obrigatório.",
            "clearance_state": "UF de desembaraço é obrigatória.",
            "clearance_date": "Data de desembaraço é obrigatória.",
            "transport_mode_code": "Via de transporte é obrigatória.",
        }.items():
            if not duimp.get(field):
                errors.append({"field": f"duimp.{field}", "message": message})
        if duimp.get("intermediation_type") in {"2", "3"}:
            if len(self._digits(duimp.get("third_party_tax_id"))) not in {11, 14}:
                errors.append(
                    {
                        "field": "duimp.third_party_tax_id",
                        "message": "CPF/CNPJ do adquirente ou encomendante é obrigatório.",
                    }
                )
            if len(str(duimp.get("third_party_state") or "")) != 2:
                errors.append(
                    {
                        "field": "duimp.third_party_state",
                        "message": "UF do adquirente ou encomendante é obrigatória.",
                    }
                )

        self._validate_fiscal_party(payload.get("issuer") or {}, errors, "issuer")
        self._validate_recipient(payload.get("recipient") or {}, errors)

        items = payload.get("items") or []
        if not items:
            errors.append({"field": "items", "message": "A NF-e precisa ter ao menos um item."})

        for index, item in enumerate(items, start=1):
            prefix = f"items[{index}]"
            description = str(item.get("description") or "").strip()
            if not description:
                errors.append({"field": f"{prefix}.description", "message": "Descrição do item é obrigatória."})
            elif description.casefold() == "mercadoria importada":
                errors.append(
                    {
                        "field": f"{prefix}.description",
                        "message": (
                            "Produto não enriquecido pelo Catálogo de Produtos."
                        ),
                    }
                )
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
            taxes = item.get("tax_payload") or {}
            missing_taxes = [
                tax for tax in ("icms", "ipi", "ii", "pis", "cofins")
                if not taxes.get(tax)
            ]
            if missing_taxes:
                errors.append(
                    {
                        "field": f"{prefix}.tax_payload",
                        "message": "Tributos obrigatórios ausentes: " + ", ".join(missing_taxes) + ".",
                    }
                )

        reconciliation = payload.get("reconciliation") or {}
        if reconciliation.get("status") == "requires_review":
            failed_names = ", ".join(
                str(check.get("name"))
                for check in reconciliation.get("checks") or []
                if not check.get("matches")
            )
            errors.append(
                {
                    "field": "reconciliation",
                    "message": (
                        "A reconciliação fiscal encontrou divergências"
                        + (f": {failed_names}." if failed_names else ".")
                    ),
                }
            )

        warnings.append(
            {
                "field": "tax_rules",
                "message": "Revisar a parametrização tributária e as regras estaduais antes da autorização da NF-e.",
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

    def _validate_recipient(
        self, party: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        if party.get("party_type") != "foreign":
            self._validate_fiscal_party(party, errors, "recipient")
            return

        if not party.get("legal_name"):
            errors.append(
                {
                    "field": "recipient.legal_name",
                    "message": "Nome do fornecedor estrangeiro é obrigatório.",
                }
            )
        address = party.get("address") or {}
        for field, message in {
            "street": "Endereço do fornecedor estrangeiro é obrigatório.",
            "number": "Número do endereço estrangeiro é obrigatório.",
            "district": "Bairro/distrito estrangeiro é obrigatório.",
            "city_name": "Cidade estrangeira é obrigatória.",
            "country_code": "Código BACEN do país é obrigatório.",
            "country_name": "Nome do país é obrigatório.",
        }.items():
            if not address.get(field):
                errors.append({"field": f"recipient.address.{field}", "message": message})
        if address.get("state") != "EX":
            errors.append(
                {
                    "field": "recipient.address.state",
                    "message": "UF de destinatário estrangeiro deve ser EX.",
                }
            )
        if address.get("city_code") != "9999999":
            errors.append(
                {
                    "field": "recipient.address.city_code",
                    "message": "Código de município do exterior deve ser 9999999.",
                }
            )

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
