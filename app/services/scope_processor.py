from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import distinct, func

from app.extensions import db
from app.models import (
    AssignmentRole,
    Client,
    ClientContact,
    DestinationPurpose,
    LocationType,
    OperationType,
    OrganizationSetting,
    Preposto,
    PricingType,
    Scope,
    ScopeAfrmmProfile,
    ScopeAssignment,
    ScopeFederalTaxProfile,
    ScopeFinancialProfile,
    ScopeGeneralProfile,
    ScopeIcmsDestinationRate,
    ScopeIcmsProfile,
    ScopeOperationAuthority,
    ScopeOperationDestinationPurpose,
    ScopeOperationDetail,
    ScopeOperationLocation,
    ScopeOperationNcm,
    ScopeOperationProfile,
    ScopePreposto,
    ScopePrepostoCity,
    ScopeRefundBankAccount,
    ScopeService,
    ScopeServiceCertificateDetail,
    ScopeServiceCustomsBrokerDetail,
    ScopeServiceFreightDetail,
    ScopeServiceInsuranceDetail,
    ScopeStatus,
    ScopeVersion,
    ServiceCatalog,
    ServiceDetailType,
    ServiceOperationType,
    ServiceType,
    TaxRegime,
    User,
)


class ScopePublishValidationError(ValueError):
    def __init__(self, errors: dict[str, list[str]]):
        self.errors = errors
        super().__init__("Erro de validação ao publicar escopo.")


@dataclass
class ScopeSyncResult:
    scope_id: str
    already_synced: bool
    changed: bool
    dry_run: bool
    missing: dict[str, list[str]] = field(default_factory=dict)
    created: dict[str, int] = field(default_factory=dict)
    updated: dict[str, int] = field(default_factory=dict)
    deactivated: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scopeId": self.scope_id,
            "alreadySynced": self.already_synced,
            "changed": self.changed,
            "dryRun": self.dry_run,
            "missing": self.missing,
            "created": self.created,
            "updated": self.updated,
            "deactivated": self.deactivated,
        }


class ScopeDataProcessor:
    """Materializa o draft canônico do escopo em tabelas relacionais.

    Regra de arquitetura:
    - save_draft(): salva somente Scope.draft.
    - publish_scope(): valida Scope.draft e sincroniza Client, contatos,
      assignments, operações, impostos, serviços, prepostos, financeiro e geral.
    """

    DEFAULT_SETTINGS = {
        "salarioMinimoVigente": 0,
        "dadosBancariosCasco": {"banco": "", "agencia": "", "conta": ""},
    }

    MANAGED_ASSIGNMENT_ROLES = {
        AssignmentRole.COMMERCIAL_RESPONSIBLE.value,
        AssignmentRole.IMPORT_DA_ANALYST.value,
        AssignmentRole.IMPORT_AE_ANALYST.value,
        AssignmentRole.EXPORT_DA_ANALYST.value,
        AssignmentRole.EXPORT_AE_ANALYST.value,
    }

    BULK_ASSIGNMENT_GROUPS = {
        "responsavel_comercial": {
            "scope_field": "commercial_responsible_user_id",
            "roles": (AssignmentRole.COMMERCIAL_RESPONSIBLE.value,),
            "draft_path": ("assignments", "commercialResponsibleId"),
        },
        "analista_da": {
            "roles": (AssignmentRole.IMPORT_DA_ANALYST.value, AssignmentRole.EXPORT_DA_ANALYST.value),
            "draft_paths": (
                ("assignments", "importDaAnalystIds"),
                ("assignments", "exportDaAnalystIds"),
            ),
        },
        "analista_ae": {
            "roles": (AssignmentRole.IMPORT_AE_ANALYST.value, AssignmentRole.EXPORT_AE_ANALYST.value),
            "draft_paths": (
                ("assignments", "importAeAnalystIds"),
                ("assignments", "exportAeAnalystIds"),
            ),
        },
    }

    SERVICE_LABELS = {
        ServiceType.CUSTOMS_CLEARANCE.value: "Despacho Aduaneiro",
        ServiceType.PREPOSTO.value: "Preposto",
        ServiceType.LI_LPCO_ISSUANCE.value: "Emissão LI/LPCO",
        ServiceType.PRODUCT_CATALOG_REGISTRATION.value: "Cadastro Catálogo de Produtos",
        ServiceType.CONSULTING.value: "Assessoria",
        ServiceType.INTERNATIONAL_FREIGHT.value: "Frete Internacional",
        ServiceType.INTERNATIONAL_INSURANCE.value: "Seguro Internacional",
        ServiceType.ROAD_FREIGHT.value: "Frete Rodoviário",
        ServiceType.NFE_ISSUANCE.value: "Emissão NF-e",
        ServiceType.ORIGIN_CERTIFICATE.value: "Certificado de Origem",
        ServiceType.PHYTOSANITARY_CERTIFICATE.value: "Certificado Fitossanitário",
        ServiceType.OTHER_CERTIFICATE.value: "Outros Certificados",
        ServiceType.SPECIAL_REGIME.value: "Regime Especial",
        ServiceType.OTHER.value: "Outro Serviço",
    }

    def __init__(self, current_user=None):
        self.current_user = current_user

    @property
    def organization_id(self):
        return getattr(self.current_user, "organization_id", None)

    @property
    def user_id(self):
        return getattr(self.current_user, "id", None)

    # ------------------------------------------------------------------
    # Draft canônico
    # ------------------------------------------------------------------
    def build_default_canonical_scope_draft(self) -> dict[str, Any]:
        return {
            "company": {
                "taxId": "",
                "legalName": "",
                "tradeName": None,
                "stateRegistration": None,
                "municipalRegistration": None,
                "officeAddress": None,
                "warehouseAddress": None,
                "mainCnae": None,
                "secondaryCnae": None,
                "taxRegime": None,
                "radarMode": None,
            },
            "contacts": [],
            "assignments": {
                "commercialResponsibleId": None,
                "importDaAnalystIds": [],
                "importAeAnalystIds": [],
                "exportDaAnalystIds": [],
                "exportAeAnalystIds": [],
            },
            "operations": {
                "types": [],
                "importOperation": None,
                "exportOperation": None,
            },
            "taxes": {
                "importTaxes": None,
                "exportTaxes": None,
            },
            "services": {
                "items": [],
                "prepostos": [],
            },
            "financial": {
                "paymentPreference": None,
                "refundPixKey": None,
                "refundBankAccounts": [],
                "notes": None,
            },
            "general": {
                "description": None,
            },
        }

    def get_admin_settings(self) -> dict:
        if not self.organization_id:
            return deepcopy(self.DEFAULT_SETTINGS)

        row = OrganizationSetting.query.filter_by(
            organization_id=self.organization_id,
            key="scope_fixed_info",
        ).first()
        return row.value_json if row and row.value_json else deepcopy(self.DEFAULT_SETTINGS)

    def normalize_draft(self, draft: dict | None) -> dict:
        base = self.build_default_canonical_scope_draft()
        incoming = draft if isinstance(draft, dict) else {}

        if self._looks_like_legacy_draft(incoming):
            incoming = self.legacy_draft_to_canonical(incoming)

        normalized = self._deep_merge(base, incoming)
        normalized["fixedInfo"] = self.get_admin_settings()
        return normalized

    def build_form_scope_from_draft(self, draft: dict | None) -> dict:
        return self.normalize_draft(draft or {})

    def save_draft(self, scope: Scope, payload: dict) -> Scope:
        scope.draft = self.normalize_draft(payload)
        if scope.status != ScopeStatus.ARCHIVED.value:
            scope.status = ScopeStatus.DRAFT.value
        return scope

    def _looks_like_legacy_draft(self, draft: dict) -> bool:
        return any(key in draft for key in ("sobreEmpresa", "contatos", "operacao", "servicos", "financeiro", "geral"))

    def _deep_merge(self, base: dict, override: dict) -> dict:
        result = deepcopy(base)
        for key, value in (override or {}).items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    # Compatibilidade temporária com o draft antigo em português.
    def legacy_draft_to_canonical(self, legacy: dict) -> dict:
        sobre_empresa = legacy.get("sobreEmpresa") or {}
        contatos = legacy.get("contatos") or []
        operacao = legacy.get("operacao") or {}
        importacao = operacao.get("importacao") or {}
        exportacao = operacao.get("exportacao") or {}
        financeiro = legacy.get("financeiro") or {}
        geral = legacy.get("geral") or {}

        return {
            "company": {
                "taxId": sobre_empresa.get("cnpj") or "",
                "legalName": sobre_empresa.get("razaoSocial") or "",
                "tradeName": sobre_empresa.get("nomeResumido"),
                "stateRegistration": sobre_empresa.get("inscricaoEstadual"),
                "municipalRegistration": sobre_empresa.get("inscricaoMunicipal"),
                "officeAddress": sobre_empresa.get("enderecoCompletoEscritorio"),
                "warehouseAddress": sobre_empresa.get("enderecoCompletoArmazem"),
                "mainCnae": sobre_empresa.get("cnaePrincipal"),
                "secondaryCnae": sobre_empresa.get("cnaeSecundario"),
                "taxRegime": sobre_empresa.get("regimeTributacao"),
                "radarMode": sobre_empresa.get("modalidadeRadar"),
            },
            "contacts": [
                {
                    "id": item.get("id"),
                    "name": item.get("nome") or item.get("name") or "",
                    "departmentRole": item.get("cargoDepartamento") or item.get("departmentRole"),
                    "email": item.get("email"),
                    "phone": item.get("telefone") or item.get("phone"),
                    "whatsapp": item.get("whatsapp"),
                    "primary": bool(item.get("principal") or item.get("primary")),
                    "active": item.get("active") is not False,
                }
                for item in contatos
                if isinstance(item, dict)
            ],
            "assignments": {
                "commercialResponsibleId": sobre_empresa.get("responsavelComercial") or sobre_empresa.get("responsavelComercialId"),
                "importDaAnalystIds": importacao.get("analistaDA") or [],
                "importAeAnalystIds": importacao.get("analistaAE") or [],
                "exportDaAnalystIds": exportacao.get("analistaDA") or [],
                "exportAeAnalystIds": exportacao.get("analistaAE") or [],
            },
            "operations": {
                "types": operacao.get("tipos") or [],
                "importOperation": self._legacy_operation_to_canonical(OperationType.IMPORT.value, importacao),
                "exportOperation": self._legacy_operation_to_canonical(OperationType.EXPORT.value, exportacao),
            },
            "taxes": {"importTaxes": None, "exportTaxes": None},
            "services": self._legacy_services_to_canonical(legacy.get("servicos") or {}),
            "financial": {
                "paymentPreference": financeiro.get("preferencia"),
                "refundPixKey": financeiro.get("chavePIXClienteDevolucaoSaldo"),
                "refundBankAccounts": [
                    {
                        "bankName": item.get("banco"),
                        "branch": item.get("agencia"),
                        "account": item.get("conta"),
                    }
                    for item in financeiro.get("dadosBancariosClienteDevolucaoSaldo") or []
                    if isinstance(item, dict)
                ],
                "notes": financeiro.get("observacoesFinanceiro"),
            },
            "general": {"description": geral.get("descricao")},
        }

    def _legacy_operation_to_canonical(self, operation_type: str, payload: dict | None) -> dict | None:
        if not isinstance(payload, dict) or not payload:
            return None
        return {
            "operationType": operation_type,
            "productsDescription": payload.get("produtosImportados") or payload.get("produtosExportados"),
            "ncmNotes": payload.get("observacaoNcms"),
            "hasExporterRelationship": self._to_bool_or_none(payload.get("vinculoComExportador")),
            "requiresDtc": self._to_bool_or_none(payload.get("necessidadeDtc")),
            "requiresDta": self._to_bool_or_none(payload.get("necessidadeDta")),
            "requiresLiLpco": self._to_bool_or_none(payload.get("necessidadeLiLpco")),
            "otherAuthority": payload.get("outroOrgaoAnuente"),
            "ncms": [
                {"code": item.get("codigo"), "description": item.get("descricao")}
                for item in payload.get("ncms") or []
                if isinstance(item, dict) and item.get("codigo")
            ],
            "entryLocations": self._legacy_locations_to_canonical(payload.get("locaisEntrada") or [], LocationType.ENTRY.value),
            "customsClearanceLocations": self._legacy_locations_to_canonical(payload.get("locaisDesembaraco") or [], LocationType.CUSTOMS_CLEARANCE.value),
            "authorities": [{"code": None, "name": str(value)} for value in payload.get("anuencias") or [] if value],
            "destinationPurposes": [
                {"purpose": value, "consumptionSubtype": None}
                for value in payload.get("destinacao") or []
                if value
            ],
        }

    def _legacy_locations_to_canonical(self, values: list[Any], location_type: str) -> list[dict[str, Any]]:
        result = []
        for value in values:
            if not value:
                continue
            raw = str(value)
            code = raw.split("|", 1)[0] if "|" in raw else None
            name = raw.split("|", 1)[1] if "|" in raw else raw
            result.append({"type": location_type, "code": code, "name": name, "rawValue": raw})
        return result

    def _legacy_services_to_canonical(self, servicos: dict) -> dict:
        # Conversor conservador: preserva apenas serviços habilitados com valores básicos.
        items = []
        for group_key, operation_type in (("importacao", "IMPORT"), ("exportacao", "EXPORT")):
            group = servicos.get(group_key) or {}
            if not isinstance(group, dict):
                continue
            for service_key, payload in group.items():
                if service_key == "preposto" or not isinstance(payload, dict) or payload.get("habilitado") is not True:
                    continue
                service_type = self._legacy_service_key_to_service_type(service_key)
                if not service_type:
                    continue
                items.append(
                    {
                        "operationType": operation_type,
                        "serviceType": service_type,
                        "enabled": True,
                        "pricingType": self._legacy_pricing_type(payload),
                        "amount": payload.get("valor") or payload.get("valorMinimo"),
                        "currency": payload.get("moeda") or "BRL",
                        "responsibleUserId": payload.get("responsavel"),
                        "lastUpdatedOn": payload.get("ultimaAtualizacao"),
                        "notes": payload.get("observacao") or payload.get("observacaoGeral"),
                        "details": None,
                    }
                )
        return {"items": items, "prepostos": []}

    def _legacy_service_key_to_service_type(self, key: str) -> str | None:
        mapping = {
            "despachoAduaneiroImportacao": ServiceType.CUSTOMS_CLEARANCE.value,
            "despachoAduaneiroExportacao": ServiceType.CUSTOMS_CLEARANCE.value,
            "emissaoLiLpco": ServiceType.LI_LPCO_ISSUANCE.value,
            "cadastroCatalogoProdutos": ServiceType.PRODUCT_CATALOG_REGISTRATION.value,
            "assessoria": ServiceType.CONSULTING.value,
            "freteInternacional": ServiceType.INTERNATIONAL_FREIGHT.value,
            "seguroInternacional": ServiceType.INTERNATIONAL_INSURANCE.value,
            "freteRodoviario": ServiceType.ROAD_FREIGHT.value,
            "emissaoNfe": ServiceType.NFE_ISSUANCE.value,
            "certificadoOrigem": ServiceType.ORIGIN_CERTIFICATE.value,
            "certificadoFitossanitario": ServiceType.PHYTOSANITARY_CERTIFICATE.value,
            "outrosCertificados": ServiceType.OTHER_CERTIFICATE.value,
        }
        return mapping.get(key)

    def _legacy_pricing_type(self, payload: dict) -> str | None:
        tipo = payload.get("tipoValor")
        if tipo:
            return tipo
        if payload.get("percentualSobreCfr") not in (None, ""):
            return PricingType.PERCENTAGE.value
        if payload.get("modalidade"):
            return PricingType.CASE_BY_CASE.value
        if payload.get("valor") not in (None, ""):
            return PricingType.FIXED.value
        return None

    # ------------------------------------------------------------------
    # Publicação
    # ------------------------------------------------------------------
    def validate_draft_for_publish(self, draft: dict) -> None:
        errors: dict[str, list[str]] = {}
        company = draft.get("company") or {}
        operations = draft.get("operations") or {}
        operation_types = operations.get("types") or []

        if not company.get("taxId"):
            errors.setdefault("company", []).append("CNPJ é obrigatório para publicar.")
        if not company.get("legalName"):
            errors.setdefault("company", []).append("Razão social é obrigatória para publicar.")
        if not operation_types:
            errors.setdefault("operations", []).append("Selecione ao menos um tipo de operação.")
        if OperationType.IMPORT.value in operation_types and not operations.get("importOperation"):
            errors.setdefault("operations", []).append("Dados de importação são obrigatórios.")
        if OperationType.EXPORT.value in operation_types and not operations.get("exportOperation"):
            errors.setdefault("operations", []).append("Dados de exportação são obrigatórios.")

        if errors:
            raise ScopePublishValidationError(errors)

    def publish_scope(self, scope: Scope) -> dict[str, Any]:
        now = datetime.utcnow()
        normalized_draft = self.normalize_draft(scope.draft or {})

        self.validate_draft_for_publish(normalized_draft)
        self.apply_draft_to_scope(scope, normalized_draft)

        client = self.upsert_client_from_draft(scope, normalized_draft)
        if not client:
            raise ScopePublishValidationError({"company": ["Informe CNPJ e razão social antes de publicar."]})

        contact_counters = self.sync_contacts_from_draft(client, normalized_draft)
        assignment_counters = self.sync_assignments_from_draft(scope, normalized_draft)
        operation_counters = self.sync_operations_from_draft(scope, normalized_draft)
        tax_counters = self.sync_taxes_from_draft(scope, normalized_draft)
        service_counters = self.sync_services_from_draft(scope, normalized_draft)
        preposto_counters = self.sync_prepostos_from_draft(scope, normalized_draft)
        financial_counters = self.sync_financial_from_draft(scope, normalized_draft)
        general_counters = self.sync_general_from_draft(scope, normalized_draft)

        scope.draft = normalized_draft
        scope.status = ScopeStatus.PUBLISHED.value
        scope.last_published_at = now
        scope.version = (scope.version or 0) + 1

        db.session.flush()
        db.session.add(
            ScopeVersion(
                scope_id=scope.id,
                version_number=scope.version,
                snapshot=normalized_draft,
                created_by_id=self.user_id,
            )
        )

        return {
            "scope_id": str(scope.id),
            "published_at": now.isoformat() + "Z",
            "client_id": str(client.id),
            "version": scope.version,
            "sync": {
                "contacts": contact_counters,
                "assignments": assignment_counters,
                "operations": operation_counters,
                "taxes": tax_counters,
                "services": service_counters,
                "prepostos": preposto_counters,
                "financial": financial_counters,
                "general": general_counters,
            },
        }

    def scope_query_for_current_user(self):
        query = Scope.query
        if self.organization_id:
            query = query.filter(Scope.organization_id == self.organization_id)
        return query

    def build_scope_summary(self, scope: Scope) -> dict:
        return {
            "id": str(scope.id),
            "status": str(scope.status),
            "version": scope.version,
            "updated_at": scope.updated_at,
            "last_published_at": scope.last_published_at,
            "client_id": str(scope.client_id) if scope.client_id else None,
            "client_cnpj": scope.client.tax_id if scope.client else None,
            "client_razao_social": scope.client.legal_name if scope.client else None,
            "responsible_user_id": str(scope.commercial_responsible_user_id) if scope.commercial_responsible_user_id else None,
            "responsible_user_nome": scope.commercial_responsible_user.name if scope.commercial_responsible_user else None,
        }

    def apply_draft_to_scope(self, scope: Scope, normalized_draft: dict) -> Scope:
        assignments = normalized_draft.get("assignments") or {}
        scope.draft = normalized_draft
        scope.commercial_responsible_user_id = assignments.get("commercialResponsibleId") or None
        return scope

    # ------------------------------------------------------------------
    # Client / contatos
    # ------------------------------------------------------------------
    def upsert_client_from_draft(self, scope: Scope, normalized_draft: dict) -> Client | None:
        company = normalized_draft.get("company") or {}
        tax_id = (company.get("taxId") or "").strip()
        legal_name = (company.get("legalName") or "").strip()

        if not tax_id or not legal_name or not scope.organization_id:
            return None

        client = Client.query.filter_by(organization_id=scope.organization_id, tax_id=tax_id).first()
        if not client:
            client = Client(organization_id=scope.organization_id, tax_id=tax_id, legal_name=legal_name)
            db.session.add(client)

        client.legal_name = legal_name
        client.trade_name = company.get("tradeName")
        client.state_registration = company.get("stateRegistration")
        client.municipal_registration = company.get("municipalRegistration")
        client.office_address = company.get("officeAddress")
        client.warehouse_address = company.get("warehouseAddress")
        client.main_cnae = company.get("mainCnae")
        client.secondary_cnae = company.get("secondaryCnae")
        client.tax_regime = company.get("taxRegime")
        client.radar_mode = company.get("radarMode")
        client.active = True

        scope.client = client
        return client

    def sync_contacts_from_draft(self, client: Client, draft: dict) -> dict[str, int]:
        contacts = draft.get("contacts") or []
        counters = {"created": 0, "updated": 0, "deactivated": 0}
        seen_ids: set[str] = set()

        for payload in contacts:
            if not isinstance(payload, dict) or not payload.get("name"):
                continue

            contact = None
            contact_id = payload.get("id")
            if contact_id:
                contact = ClientContact.query.filter_by(id=contact_id, client_id=client.id).first()

            if not contact:
                contact = ClientContact(client=client)
                db.session.add(contact)
                counters["created"] += 1
            else:
                counters["updated"] += 1

            contact.name = payload.get("name")
            contact.department_role = payload.get("departmentRole")
            contact.email = payload.get("email")
            contact.phone = payload.get("phone")
            contact.whatsapp = payload.get("whatsapp")
            contact.primary = bool(payload.get("primary"))
            contact.active = payload.get("active") is not False
            db.session.flush()
            seen_ids.add(str(contact.id))

        for contact in ClientContact.query.filter_by(client_id=client.id, active=True).all():
            if seen_ids and str(contact.id) not in seen_ids:
                contact.active = False
                counters["deactivated"] += 1

        return counters

    # ------------------------------------------------------------------
    # Assignments
    # ------------------------------------------------------------------
    def _extract_assignment_targets(self, draft: dict) -> list[tuple[str, str]]:
        assignments = draft.get("assignments") or {}
        targets: list[tuple[str, str]] = []

        commercial = assignments.get("commercialResponsibleId")
        if commercial:
            targets.append((commercial, AssignmentRole.COMMERCIAL_RESPONSIBLE.value))

        for user_id in assignments.get("importDaAnalystIds") or []:
            if user_id:
                targets.append((user_id, AssignmentRole.IMPORT_DA_ANALYST.value))
        for user_id in assignments.get("importAeAnalystIds") or []:
            if user_id:
                targets.append((user_id, AssignmentRole.IMPORT_AE_ANALYST.value))
        for user_id in assignments.get("exportDaAnalystIds") or []:
            if user_id:
                targets.append((user_id, AssignmentRole.EXPORT_DA_ANALYST.value))
        for user_id in assignments.get("exportAeAnalystIds") or []:
            if user_id:
                targets.append((user_id, AssignmentRole.EXPORT_AE_ANALYST.value))

        deduped: list[tuple[str, str]] = []
        seen = set()
        for user_id, role in targets:
            key = (str(user_id), role)
            if key not in seen:
                deduped.append(key)
                seen.add(key)
        return deduped

    def sync_assignments_from_draft(self, scope: Scope, draft: dict) -> dict[str, int]:
        now = datetime.utcnow()
        desired = self._extract_assignment_targets(draft)
        desired_keys = {(user_id, role) for user_id, role in desired}
        counters = {"created": 0, "updated": 0, "deactivated": 0}

        active_assignments = ScopeAssignment.query.filter(
            ScopeAssignment.scope_id == scope.id,
            ScopeAssignment.role.in_(self.MANAGED_ASSIGNMENT_ROLES),
            ScopeAssignment.active.is_(True),
        ).all()

        for assignment in active_assignments:
            key = (str(assignment.user_id), str(assignment.role))
            if key not in desired_keys:
                assignment.active = False
                assignment.ends_at = now
                counters["deactivated"] += 1

        for user_id, role in desired:
            existing = ScopeAssignment.query.filter_by(
                scope_id=scope.id,
                user_id=user_id,
                role=role,
                active=True,
            ).first()
            if existing:
                counters["updated"] += 1
                continue
            db.session.add(
                ScopeAssignment(scope_id=scope.id, user_id=user_id, role=role, active=True, starts_at=now)
            )
            counters["created"] += 1

        return counters

    # ------------------------------------------------------------------
    # Operações
    # ------------------------------------------------------------------
    def sync_operations_from_draft(self, scope: Scope, draft: dict) -> dict[str, int]:
        operations = draft.get("operations") or {}
        types = {str(value) for value in operations.get("types") or [] if value}
        counters = {"created": 0, "updated": 0, "deleted": 0}

        profile = ScopeOperationProfile.query.filter_by(scope_id=scope.id).first()
        if not profile:
            profile = ScopeOperationProfile(scope_id=scope.id)
            db.session.add(profile)
        profile.has_import = OperationType.IMPORT.value in types
        profile.has_export = OperationType.EXPORT.value in types

        for existing in list(scope.operation_details):
            if str(existing.operation_type) not in types:
                db.session.delete(existing)
                counters["deleted"] += 1

        for operation_type, key in (
            (OperationType.IMPORT.value, "importOperation"),
            (OperationType.EXPORT.value, "exportOperation"),
        ):
            payload = operations.get(key)
            if operation_type not in types or not isinstance(payload, dict):
                continue
            result = self._upsert_scope_operation(scope, operation_type, payload)
            counters[result] += 1

        return counters

    def _upsert_scope_operation(self, scope: Scope, operation_type: str, payload: dict) -> str:
        operation = ScopeOperationDetail.query.filter_by(scope_id=scope.id, operation_type=operation_type).first()
        created = False
        if not operation:
            operation = ScopeOperationDetail(scope_id=scope.id, operation_type=operation_type)
            db.session.add(operation)
            created = True

        operation.products_description = payload.get("productsDescription")
        operation.ncm_notes = payload.get("ncmNotes")
        operation.has_exporter_relationship = payload.get("hasExporterRelationship")
        operation.requires_dtc = payload.get("requiresDtc")
        operation.requires_dta = payload.get("requiresDta")
        operation.requires_li_lpco = payload.get("requiresLiLpco")
        operation.other_authority = payload.get("otherAuthority")
        db.session.flush()

        self._replace_operation_ncms(operation, payload.get("ncms") or [])
        self._replace_operation_locations(operation, payload.get("entryLocations") or [], LocationType.ENTRY.value)
        self._replace_operation_locations(operation, payload.get("customsClearanceLocations") or [], LocationType.CUSTOMS_CLEARANCE.value)
        self._replace_operation_authorities(operation, payload.get("authorities") or [])
        self._replace_operation_destination_purposes(operation, payload.get("destinationPurposes") or [])
        return "created" if created else "updated"

    def _replace_operation_ncms(self, operation: ScopeOperationDetail, items: list[dict]) -> None:
        operation.ncms = []
        for item in items:
            if isinstance(item, dict) and item.get("code"):
                operation.ncms.append(ScopeOperationNcm(code=item.get("code"), description=item.get("description")))

    def _replace_operation_locations(self, operation: ScopeOperationDetail, items: list[dict], location_type: str) -> None:
        operation.locations = [loc for loc in operation.locations if str(loc.location_type) != location_type]
        for item in items:
            if isinstance(item, dict) and item.get("name"):
                operation.locations.append(
                    ScopeOperationLocation(
                        location_type=location_type,
                        code=item.get("code"),
                        name=item.get("name"),
                        raw_value=item.get("rawValue") or item.get("raw_value"),
                    )
                )

    def _replace_operation_authorities(self, operation: ScopeOperationDetail, items: list[dict]) -> None:
        operation.authorities = []
        for item in items:
            if isinstance(item, dict) and item.get("name"):
                operation.authorities.append(ScopeOperationAuthority(code=item.get("code"), name=item.get("name")))

    def _replace_operation_destination_purposes(self, operation: ScopeOperationDetail, items: list[dict]) -> None:
        operation.destination_purposes = []
        for item in items:
            if isinstance(item, dict) and item.get("purpose"):
                operation.destination_purposes.append(
                    ScopeOperationDestinationPurpose(
                        purpose=item.get("purpose"),
                        consumption_subtype=item.get("consumptionSubtype") or item.get("consumption_subtype"),
                    )
                )

    def _operation_for_type(self, scope: Scope, operation_type: str) -> ScopeOperationDetail | None:
        return ScopeOperationDetail.query.filter_by(scope_id=scope.id, operation_type=operation_type).first()

    # ------------------------------------------------------------------
    # Impostos
    # ------------------------------------------------------------------
    def sync_taxes_from_draft(self, scope: Scope, draft: dict) -> dict[str, int]:
        taxes = draft.get("taxes") or {}
        counters = {"created": 0, "updated": 0, "deleted": 0}

        for operation_type, key in ((OperationType.IMPORT.value, "importTaxes"), (OperationType.EXPORT.value, "exportTaxes")):
            operation = self._operation_for_type(scope, operation_type)
            payload = taxes.get(key)
            if not operation:
                continue
            result = self._sync_operation_taxes(operation, payload if isinstance(payload, dict) else {})
            for counter_key, value in result.items():
                counters[counter_key] += value

        return counters

    def _sync_operation_taxes(self, operation: ScopeOperationDetail, payload: dict) -> dict[str, int]:
        counters = {"created": 0, "updated": 0, "deleted": 0}
        counters[self._upsert_or_delete_federal_taxes(operation, payload.get("federalTaxes"))] += 1
        counters[self._upsert_or_delete_afrmm(operation, payload.get("afrmm"))] += 1
        counters[self._upsert_or_delete_icms(operation, payload.get("icms"))] += 1
        return {key: value for key, value in counters.items() if value}

    def _upsert_or_delete_federal_taxes(self, operation: ScopeOperationDetail, payload: dict | None) -> str:
        existing = operation.federal_tax_profile
        if not isinstance(payload, dict):
            if existing:
                db.session.delete(existing)
                return "deleted"
            return "updated"
        created = False
        if not existing:
            existing = ScopeFederalTaxProfile(operation_detail=operation)
            db.session.add(existing)
            created = True
        existing.payment_account_type = payload.get("paymentAccountType") or "CASCO"
        existing.bank_name = payload.get("bankName")
        existing.bank_branch = payload.get("bankBranch")
        existing.bank_account = payload.get("bankAccount")
        existing.ii_regime = payload.get("iiRegime")
        existing.ii_benefit_detail = payload.get("iiBenefitDetail")
        existing.ipi_regime = payload.get("ipiRegime")
        existing.ipi_benefit_detail = payload.get("ipiBenefitDetail")
        existing.pis_regime = payload.get("pisRegime")
        existing.pis_benefit_detail = payload.get("pisBenefitDetail")
        existing.cofins_regime = payload.get("cofinsRegime")
        existing.cofins_benefit_detail = payload.get("cofinsBenefitDetail")
        existing.notes = payload.get("notes")
        return "created" if created else "updated"

    def _upsert_or_delete_afrmm(self, operation: ScopeOperationDetail, payload: dict | None) -> str:
        existing = operation.afrmm_profile
        if not isinstance(payload, dict):
            if existing:
                db.session.delete(existing)
                return "deleted"
            return "updated"
        created = False
        if not existing:
            existing = ScopeAfrmmProfile(operation_detail=operation)
            db.session.add(existing)
            created = True
        existing.payment_account_type = payload.get("paymentAccountType") or "CASCO"
        existing.bank_name = payload.get("bankName")
        existing.bank_branch = payload.get("bankBranch")
        existing.bank_account = payload.get("bankAccount")
        existing.regime = payload.get("regime")
        existing.benefit_detail = payload.get("benefitDetail")
        existing.notes = payload.get("notes")
        return "created" if created else "updated"

    def _upsert_or_delete_icms(self, operation: ScopeOperationDetail, payload: dict | None) -> str:
        existing = operation.icms_profile
        if not isinstance(payload, dict):
            if existing:
                db.session.delete(existing)
                return "deleted"
            return "updated"
        created = False
        if not existing:
            existing = ScopeIcmsProfile(operation_detail=operation)
            db.session.add(existing)
            created = True
        existing.payment_account_type = payload.get("paymentAccountType") or "CASCO"
        existing.bank_name = payload.get("bankName")
        existing.bank_branch = payload.get("bankBranch")
        existing.bank_account = payload.get("bankAccount")
        existing.regime = payload.get("regime")
        existing.collected_rate = self._to_decimal(payload.get("collectedRate"))
        existing.effective_rate = self._to_decimal(payload.get("effectiveRate"))
        existing.notes = payload.get("notes")
        existing.destination_rates = []
        for rate in payload.get("destinationRates") or []:
            if isinstance(rate, dict) and rate.get("destinationPurpose"):
                existing.destination_rates.append(
                    ScopeIcmsDestinationRate(
                        destination_purpose=rate.get("destinationPurpose"),
                        collected_rate=self._to_decimal(rate.get("collectedRate")),
                        effective_rate=self._to_decimal(rate.get("effectiveRate")),
                        notes=rate.get("notes"),
                    )
                )
        return "created" if created else "updated"

    # ------------------------------------------------------------------
    # Serviços
    # ------------------------------------------------------------------
    def _catalog_code(self, operation_type: str, service_type: str) -> str:
        return f"{operation_type}:{service_type}"

    def _service_name(self, operation_type: str, service_type: str) -> str:
        suffix = "Import" if operation_type == ServiceOperationType.IMPORT.value else "Export" if operation_type == ServiceOperationType.EXPORT.value else "Both"
        return f"{self.SERVICE_LABELS.get(service_type, service_type)} - {suffix}"

    def _get_or_create_service_catalog(self, organization_id, operation_type: str, service_type: str) -> ServiceCatalog:
        code = self._catalog_code(operation_type, service_type)
        catalog = ServiceCatalog.query.filter_by(organization_id=organization_id, code=code).first()
        if catalog:
            catalog.name = catalog.name or self._service_name(operation_type, service_type)
            catalog.service_type = catalog.service_type or service_type
            catalog.operation_type = catalog.operation_type or operation_type
            catalog.active = True
            return catalog

        catalog = ServiceCatalog(
            organization_id=organization_id,
            code=code,
            name=self._service_name(operation_type, service_type),
            service_type=service_type,
            operation_type=operation_type,
            active=True,
        )
        db.session.add(catalog)
        db.session.flush()
        return catalog

    def _iter_enabled_service_payloads(self, draft: dict):
        for payload in ((draft.get("services") or {}).get("items") or []):
            if not isinstance(payload, dict) or payload.get("enabled") is not True:
                continue
            operation_type = payload.get("operationType")
            service_type = payload.get("serviceType")
            if operation_type and service_type:
                yield operation_type, service_type, payload

    def sync_services_from_draft(self, scope: Scope, draft: dict) -> dict[str, int]:
        seen_keys: set[tuple[str, str]] = set()
        counters = {"created": 0, "updated": 0, "deleted": 0}

        for operation_type, service_type, payload in self._iter_enabled_service_payloads(draft):
            catalog = self._get_or_create_service_catalog(scope.organization_id, operation_type, service_type)
            seen_keys.add((str(catalog.id), operation_type))

            scope_service = ScopeService.query.filter_by(
                scope_id=scope.id,
                service_catalog_id=catalog.id,
                operation_type=operation_type,
            ).first()
            if not scope_service:
                scope_service = ScopeService(scope_id=scope.id, service_catalog_id=catalog.id, operation_type=operation_type)
                db.session.add(scope_service)
                counters["created"] += 1
            else:
                counters["updated"] += 1

            scope_service.enabled = True
            scope_service.pricing_type = payload.get("pricingType")
            scope_service.amount = self._to_decimal(payload.get("amount"))
            scope_service.currency = payload.get("currency") or "BRL"
            scope_service.responsible_user_id = payload.get("responsibleUserId") or None
            scope_service.last_updated_on = self._to_date(payload.get("lastUpdatedOn"))
            scope_service.notes = payload.get("notes")
            db.session.flush()
            self._sync_service_detail(scope_service, payload.get("details"))

        for existing in ScopeService.query.filter_by(scope_id=scope.id, enabled=True).all():
            key = (str(existing.service_catalog_id), str(existing.operation_type))
            if key not in seen_keys:
                existing.enabled = False
                counters["deleted"] += 1

        return counters

    def _sync_service_detail(self, service: ScopeService, details: dict | None) -> None:
        if not isinstance(details, dict) or not details.get("type"):
            self._delete_service_details(service)
            return

        detail_type = str(details.get("type"))
        payload = self._detail_payload_by_type(details, detail_type)
        self._delete_service_details(service, except_type=detail_type)

        if detail_type == ServiceDetailType.FREIGHT.value:
            detail = service.freight_detail or ScopeServiceFreightDetail(scope_service=service)
            detail.mode = payload.get("mode")
            detail.negotiated_ptax = self._to_decimal(payload.get("negotiatedPtax"))
            detail.general_notes = payload.get("generalNotes")
            db.session.add(detail)
        elif detail_type == ServiceDetailType.INSURANCE.value:
            detail = service.insurance_detail or ScopeServiceInsuranceDetail(scope_service=service)
            detail.minimum_amount = self._to_decimal(payload.get("minimumAmount"))
            detail.cfr_percentage = self._to_decimal(payload.get("cfrPercentage"))
            detail.policy_inclusion_date = self._to_date(payload.get("policyInclusionDate"))
            detail.additional_description = payload.get("additionalDescription")
            db.session.add(detail)
        elif detail_type == ServiceDetailType.CUSTOMS_BROKER.value:
            detail = service.customs_broker_detail or ScopeServiceCustomsBrokerDetail(scope_service=service)
            detail.salary_multiplier = self._to_decimal(payload.get("salaryMultiplier"))
            detail.pricing_reference = payload.get("pricingReference")
            db.session.add(detail)
        elif detail_type == ServiceDetailType.CERTIFICATE.value:
            detail = service.certificate_detail or ScopeServiceCertificateDetail(scope_service=service)
            detail.certificate_name = payload.get("certificateName")
            detail.issuing_authority = payload.get("issuingAuthority")
            detail.notes = payload.get("notes")
            db.session.add(detail)

    def _detail_payload_by_type(self, details: dict, detail_type: str) -> dict:
        nested_key = {
            ServiceDetailType.FREIGHT.value: "freight",
            ServiceDetailType.INSURANCE.value: "insurance",
            ServiceDetailType.CUSTOMS_BROKER.value: "customsBroker",
            ServiceDetailType.CERTIFICATE.value: "certificate",
        }.get(detail_type)
        if nested_key and isinstance(details.get(nested_key), dict):
            return details[nested_key]
        return details

    def _delete_service_details(self, service: ScopeService, except_type: str | None = None) -> None:
        detail_pairs = (
            (ServiceDetailType.FREIGHT.value, service.freight_detail),
            (ServiceDetailType.INSURANCE.value, service.insurance_detail),
            (ServiceDetailType.CUSTOMS_BROKER.value, service.customs_broker_detail),
            (ServiceDetailType.CERTIFICATE.value, service.certificate_detail),
        )
        for detail_type, detail in detail_pairs:
            if detail is not None and detail_type != except_type:
                db.session.delete(detail)

    # ------------------------------------------------------------------
    # Prepostos
    # ------------------------------------------------------------------
    def sync_prepostos_from_draft(self, scope: Scope, draft: dict) -> dict[str, int]:
        prepostos = ((draft.get("services") or {}).get("prepostos") or [])
        counters = {"created": 0, "updated": 0, "disabled": 0}
        seen_ids: set[str] = set()

        for payload in prepostos:
            if not isinstance(payload, dict) or payload.get("enabled") is not True:
                continue

            operation_type = payload.get("operationType")
            if not operation_type:
                continue

            preposto_id = payload.get("prepostoId")
            manual_name = payload.get("manualPrepostoName")

            link = None
            if preposto_id:
                link = ScopePreposto.query.filter_by(
                    scope_id=scope.id,
                    preposto_id=preposto_id,
                    operation_type=operation_type,
                ).first()
            elif manual_name:
                link = ScopePreposto.query.filter_by(
                    scope_id=scope.id,
                    preposto_id=None,
                    operation_type=operation_type,
                    manual_preposto_name=manual_name,
                ).first()

            if not link:
                link = ScopePreposto(scope_id=scope.id, preposto_id=preposto_id or None, operation_type=operation_type)
                db.session.add(link)
                counters["created"] += 1
            else:
                counters["updated"] += 1

            link.enabled = True
            link.amount = self._to_decimal(payload.get("amount"))
            link.included_in_casco_customs_clearance = payload.get("includedInCascoCustomsClearance")
            link.other_port = payload.get("otherPort")
            link.other_border = payload.get("otherBorder")
            link.notes = payload.get("notes")
            link.manual_preposto_name = manual_name
            link.manual_preposto_notes = payload.get("manualPrepostoNotes")
            link.cities = []
            for city in payload.get("cities") or []:
                if isinstance(city, dict) and city.get("city"):
                    link.cities.append(ScopePrepostoCity(city=city.get("city"), state=city.get("state")))
            db.session.flush()
            seen_ids.add(str(link.id))

        for link in ScopePreposto.query.filter_by(scope_id=scope.id, enabled=True).all():
            if str(link.id) not in seen_ids:
                link.enabled = False
                counters["disabled"] += 1

        return counters

    # ------------------------------------------------------------------
    # Financeiro / geral
    # ------------------------------------------------------------------
    def sync_financial_from_draft(self, scope: Scope, draft: dict) -> dict[str, int]:
        payload = draft.get("financial") or {}
        profile = ScopeFinancialProfile.query.filter_by(scope_id=scope.id).first()
        created = False
        if not profile:
            profile = ScopeFinancialProfile(scope_id=scope.id)
            db.session.add(profile)
            created = True

        profile.payment_preference = payload.get("paymentPreference")
        profile.refund_pix_key = payload.get("refundPixKey")
        profile.notes = payload.get("notes")
        profile.refund_bank_accounts = []
        for account in payload.get("refundBankAccounts") or []:
            if isinstance(account, dict):
                profile.refund_bank_accounts.append(
                    ScopeRefundBankAccount(
                        bank_name=account.get("bankName"),
                        branch=account.get("branch"),
                        account=account.get("account"),
                    )
                )
        return {"created": 1 if created else 0, "updated": 0 if created else 1}

    def sync_general_from_draft(self, scope: Scope, draft: dict) -> dict[str, int]:
        payload = draft.get("general") or {}
        profile = ScopeGeneralProfile.query.filter_by(scope_id=scope.id).first()
        created = False
        if not profile:
            profile = ScopeGeneralProfile(scope_id=scope.id)
            db.session.add(profile)
            created = True
        profile.description = payload.get("description")
        return {"created": 1 if created else 0, "updated": 0 if created else 1}

    # ------------------------------------------------------------------
    # Bulk assignment operations
    # ------------------------------------------------------------------
    def _bulk_group_config(self, group_by: str) -> dict[str, Any]:
        config = self.BULK_ASSIGNMENT_GROUPS.get(group_by)
        if not config:
            allowed = ", ".join(sorted(self.BULK_ASSIGNMENT_GROUPS))
            raise ValueError(f"groupBy inválido. Valores aceitos: {allowed}.")
        return config

    def _isoformat_z(self, value: datetime | None) -> str | None:
        if not value:
            return None
        return value.isoformat() + "Z"

    def _apply_org_filter_to_scope_query(self, query):
        if self.organization_id:
            return query.filter(Scope.organization_id == self.organization_id)
        return query

    def _validate_bulk_user(self, user_id: str, *, require_active: bool = False) -> User:
        query = User.query.filter(User.id == user_id)
        if self.organization_id:
            query = query.filter(User.organization_id == self.organization_id)
        if require_active:
            query = query.filter(User.active.is_(True))
        user = query.first()
        if not user:
            status = "ativo " if require_active else ""
            raise ValueError(f"Usuário {status}não encontrado na organização atual.")
        return user

    def _replace_user_in_list(self, values: Any, from_user_id: str, to_user_id: str) -> list[str]:
        if not isinstance(values, list):
            return values
        replaced: list[str] = []
        for value in values:
            normalized = str(value) if value is not None else value
            if normalized == from_user_id:
                normalized = to_user_id
            if normalized and normalized not in replaced:
                replaced.append(normalized)
        return replaced

    def _set_nested_value(self, payload: dict, path: tuple[str, ...], value: Any) -> None:
        cursor = payload
        for key in path[:-1]:
            if not isinstance(cursor.get(key), dict):
                cursor[key] = {}
            cursor = cursor[key]
        cursor[path[-1]] = value

    def _get_nested_value(self, payload: dict, path: tuple[str, ...]) -> Any:
        cursor: Any = payload
        for key in path:
            if not isinstance(cursor, dict):
                return None
            cursor = cursor.get(key)
        return cursor

    def _update_scope_draft_for_bulk_assignment(self, scope: Scope, group_by: str, from_user_id: str, to_user_id: str) -> None:
        draft = self.normalize_draft(scope.draft or {})
        config = self._bulk_group_config(group_by)
        if config.get("scope_field") == "commercial_responsible_user_id":
            self._set_nested_value(draft, ("assignments", "commercialResponsibleId"), to_user_id)
        else:
            for path in config.get("draft_paths", ()):  # type: ignore[union-attr]
                current = self._get_nested_value(draft, path)
                if isinstance(current, list):
                    self._set_nested_value(draft, path, self._replace_user_in_list(current, from_user_id, to_user_id))
        scope.draft = draft

    def _upsert_active_assignment(self, scope_id, user_id: str, role: str, now: datetime) -> None:
        existing = ScopeAssignment.query.filter_by(scope_id=scope_id, user_id=user_id, role=role, active=True).first()
        if existing:
            return
        db.session.add(ScopeAssignment(scope_id=scope_id, user_id=user_id, role=role, active=True, starts_at=now))

    def _move_active_assignments(self, scope: Scope, roles: tuple[str, ...], from_user_id: str, to_user_id: str, now: datetime) -> bool:
        source_assignments = ScopeAssignment.query.filter(
            ScopeAssignment.scope_id == scope.id,
            ScopeAssignment.user_id == from_user_id,
            ScopeAssignment.role.in_(roles),
            ScopeAssignment.active.is_(True),
        ).all()
        if not source_assignments:
            return False
        roles_to_move = {assignment.role for assignment in source_assignments}
        for assignment in source_assignments:
            assignment.active = False
            assignment.ends_at = now
        for role in roles_to_move:
            self._upsert_active_assignment(scope.id, to_user_id, role, now)
        return True

    def get_bulk_assignment_summary(self, group_by: str) -> dict[str, Any]:
        config = self._bulk_group_config(group_by)
        if config.get("scope_field") == "commercial_responsible_user_id":
            query = (
                db.session.query(
                    User.id.label("user_id"),
                    User.name.label("user_name"),
                    User.role.label("user_role"),
                    User.department.label("user_setor"),
                    func.count(Scope.id).label("total_scopes"),
                )
                .join(Scope, Scope.commercial_responsible_user_id == User.id)
            )
            if self.organization_id:
                query = query.filter(Scope.organization_id == self.organization_id)
        else:
            roles = config["roles"]
            query = (
                db.session.query(
                    User.id.label("user_id"),
                    User.name.label("user_name"),
                    User.role.label("user_role"),
                    User.department.label("user_setor"),
                    func.count(distinct(Scope.id)).label("total_scopes"),
                )
                .join(ScopeAssignment, ScopeAssignment.user_id == User.id)
                .join(Scope, Scope.id == ScopeAssignment.scope_id)
                .filter(ScopeAssignment.active.is_(True), ScopeAssignment.role.in_(roles))
            )
            if self.organization_id:
                query = query.filter(Scope.organization_id == self.organization_id)

        rows = query.group_by(User.id, User.name, User.role, User.department).order_by(User.name.asc()).all()
        items = [
            {
                "userId": str(row.user_id),
                "userName": row.user_name,
                "userRole": row.user_role,
                "userSetor": row.user_setor,
                "totalScopes": int(row.total_scopes or 0),
            }
            for row in rows
        ]
        return {"groupBy": group_by, "totalUsers": len(items), "totalScopes": sum(item["totalScopes"] for item in items), "items": items}

    def get_bulk_assignment_scopes(self, group_by: str, user_id: str) -> dict[str, Any]:
        config = self._bulk_group_config(group_by)
        self._validate_bulk_user(user_id)
        if config.get("scope_field") == "commercial_responsible_user_id":
            query = Scope.query.filter(Scope.commercial_responsible_user_id == user_id)
        else:
            scope_ids_subquery = (
                db.session.query(ScopeAssignment.scope_id)
                .filter(ScopeAssignment.user_id == user_id, ScopeAssignment.role.in_(config["roles"]), ScopeAssignment.active.is_(True))
                .distinct()
                .subquery()
            )
            query = Scope.query.join(scope_ids_subquery, Scope.id == scope_ids_subquery.c.scope_id)
        query = self._apply_org_filter_to_scope_query(query)
        scopes = query.order_by(Scope.updated_at.desc().nullslast(), Scope.created_at.desc()).all()
        return {
            "groupBy": group_by,
            "userId": str(user_id),
            "total": len(scopes),
            "items": [
                {
                    "id": str(scope.id),
                    "status": scope.status,
                    "clientName": scope.client.legal_name if scope.client else None,
                    "clientCnpj": scope.client.tax_id if scope.client else None,
                    "updatedAt": self._isoformat_z(scope.updated_at),
                }
                for scope in scopes
            ],
        }

    def bulk_update_assignment(self, group_by: str, from_user_id: str, to_user_id: str, scope_ids: list[str]) -> dict[str, Any]:
        config = self._bulk_group_config(group_by)
        if not from_user_id or not to_user_id:
            raise ValueError("fromUserId e toUserId são obrigatórios.")
        if str(from_user_id) == str(to_user_id):
            raise ValueError("fromUserId e toUserId devem ser diferentes.")
        if not isinstance(scope_ids, list) or not scope_ids:
            raise ValueError("scopeIds deve ser uma lista não vazia.")

        from_user_id = str(from_user_id)
        to_user_id = str(to_user_id)
        scope_ids = [str(scope_id) for scope_id in scope_ids if scope_id]
        if not scope_ids:
            raise ValueError("scopeIds deve conter identificadores válidos.")

        self._validate_bulk_user(from_user_id)
        self._validate_bulk_user(to_user_id, require_active=True)
        query = self._apply_org_filter_to_scope_query(Scope.query.filter(Scope.id.in_(scope_ids)))
        scopes = query.all()
        scopes_by_id = {str(scope.id): scope for scope in scopes}
        ordered_scopes = [scopes_by_id[scope_id] for scope_id in scope_ids if scope_id in scopes_by_id]
        now = datetime.utcnow()
        updated_scope_ids: list[str] = []

        for scope in ordered_scopes:
            changed = False
            if config.get("scope_field") == "commercial_responsible_user_id":
                if str(scope.commercial_responsible_user_id) != from_user_id:
                    continue
                scope.commercial_responsible_user_id = to_user_id
                self._move_active_assignments(scope, config["roles"], from_user_id, to_user_id, now)
                changed = True
            else:
                changed = self._move_active_assignments(scope, config["roles"], from_user_id, to_user_id, now)
            if changed:
                self._update_scope_draft_for_bulk_assignment(scope, group_by, from_user_id, to_user_id)
                updated_scope_ids.append(str(scope.id))

        return {"ok": True, "impactedScopes": len(updated_scope_ids), "updatedScopeIds": updated_scope_ids}

    # ------------------------------------------------------------------
    # Sync / auditoria
    # ------------------------------------------------------------------
    def get_sync_missing(self, scope: Scope, draft: dict | None = None) -> dict[str, list[str]]:
        draft = self.normalize_draft(draft or scope.draft or {})
        missing: dict[str, list[str]] = {"client": [], "assignments": [], "operations": [], "services": [], "prepostos": []}

        company = draft.get("company") or {}
        if company.get("taxId") and company.get("legalName") and not scope.client_id:
            missing["client"].append("client_id")

        for user_id, role in self._extract_assignment_targets(draft):
            exists = ScopeAssignment.query.filter_by(scope_id=scope.id, user_id=user_id, role=role, active=True).first()
            if not exists:
                missing["assignments"].append(f"{role}:{user_id}")

        operations = draft.get("operations") or {}
        for operation_type in operations.get("types") or []:
            if not self._operation_for_type(scope, operation_type):
                missing["operations"].append(operation_type)

        for operation_type, service_type, _payload in self._iter_enabled_service_payloads(draft):
            code = self._catalog_code(operation_type, service_type)
            catalog = ServiceCatalog.query.filter_by(organization_id=scope.organization_id, code=code).first()
            if not catalog:
                missing["services"].append(code)
                continue
            exists = ScopeService.query.filter_by(scope_id=scope.id, service_catalog_id=catalog.id, operation_type=operation_type, enabled=True).first()
            if not exists:
                missing["services"].append(code)

        for payload in ((draft.get("services") or {}).get("prepostos") or []):
            if not isinstance(payload, dict) or payload.get("enabled") is not True:
                continue
            operation_type = payload.get("operationType")
            preposto_id = payload.get("prepostoId")
            if preposto_id:
                exists = ScopePreposto.query.filter_by(scope_id=scope.id, preposto_id=preposto_id, operation_type=operation_type, enabled=True).first()
                if not exists:
                    missing["prepostos"].append(f"{operation_type}:{preposto_id}")

        return {key: value for key, value in missing.items() if value}

    def is_scope_synced(self, scope: Scope, draft: dict | None = None) -> bool:
        return not bool(self.get_sync_missing(scope, draft=draft))

    def sync_scope(self, scope: Scope, dry_run: bool = False) -> ScopeSyncResult:
        normalized_draft = self.normalize_draft(scope.draft or {})
        missing = self.get_sync_missing(scope, draft=normalized_draft)
        already_synced = not bool(missing)
        result = ScopeSyncResult(scope_id=str(scope.id), already_synced=already_synced, changed=False, dry_run=dry_run, missing=missing)
        if dry_run or already_synced:
            return result
        publish_result = self.publish_scope(scope)
        result.changed = True
        result.created = publish_result.get("sync", {})
        return result

    def sync_scopes(self, scopes: list[Scope], dry_run: bool = False) -> list[ScopeSyncResult]:
        return [self.sync_scope(scope, dry_run=dry_run) for scope in scopes]

    # ------------------------------------------------------------------
    # Conversões utilitárias
    # ------------------------------------------------------------------
    def _to_decimal(self, value) -> Decimal | None:
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None

    def _to_date(self, value) -> date | None:
        if value in (None, ""):
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value[:10]).date()
            except ValueError:
                return None
        return None

    def _to_bool_or_none(self, value):
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().upper()
            if normalized in ("SIM", "S", "TRUE", "1", "YES", "Y"):
                return True
            if normalized in ("NAO", "NÃO", "N", "FALSE", "0", "NO"):
                return False
            if normalized == "":
                return None
        if isinstance(value, int):
            if value == 1:
                return True
            if value == 0:
                return False
        return None
