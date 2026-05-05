from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, distinct, or_

from ..extensions import db
from ..models import Client, Scope, ScopeService, ServiceCatalog, User


class DashboardMetricsService:
    """
    Serviço de métricas para dashboards.

    Responsabilidades:
    - concentrar a lógica SQL/ORM fora das rotas;
    - aplicar isolamento por organização;
    - agregar escopos por usuário;
    - agregar serviços habilitados;
    - listar serviços por escopo.
    """

    def __init__(self, current_user: User):
        self.current_user = current_user
        self.organization_id = getattr(current_user, "organization_id", None)

    def _apply_scope_org_filter(self, query):
        if self.organization_id:
            return query.filter(Scope.organization_id == self.organization_id)
        return query

    def _apply_common_scope_filters(
        self,
        query,
        *,
        status: str | None = None,
        created_by_id: str | None = None,
        responsible_user_id: str | None = None,
        client_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ):
        query = self._apply_scope_org_filter(query)

        if status:
            query = query.filter(Scope.status == status)

        if created_by_id:
            query = query.filter(Scope.created_by_id == created_by_id)

        if responsible_user_id:
            query = query.filter(Scope.responsible_user_id == responsible_user_id)

        if client_id:
            query = query.filter(Scope.client_id == client_id)

        if date_from:
            query = query.filter(Scope.created_at >= date_from)

        if date_to:
            query = query.filter(Scope.created_at < date_to)

        return query

    @staticmethod
    def _money(value: Any) -> float | None:
        if value is None:
            return None

        if isinstance(value, Decimal):
            return float(value)

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _dt(value: datetime | None) -> str | None:
        if not value:
            return None
        return value.isoformat() + "Z"

    @staticmethod
    def _pagination(limit: int | None, offset: int | None) -> tuple[int, int]:
        safe_limit = int(limit or 50)
        safe_offset = int(offset or 0)

        if safe_limit < 1:
            safe_limit = 1

        if safe_limit > 500:
            safe_limit = 500

        if safe_offset < 0:
            safe_offset = 0

        return safe_limit, safe_offset

    def get_scopes_by_user(
        self,
        *,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        include_scopes: bool = True,
        scopes_limit_per_user: int = 50,
    ) -> dict:
        """
        Retorna quantidade de escopos cadastrados por usuário e,
        opcionalmente, quais escopos são esses.

        A contagem considera Scope.created_by_id.
        """

        base_query = (
            db.session.query(
                User.id.label("user_id"),
                User.nome.label("user_name"),
                User.email.label("user_email"),
                User.role.label("user_role"),
                User.setor.label("user_setor"),
                func.count(Scope.id).label("total_scopes"),
            )
            .join(Scope, Scope.created_by_id == User.id)
        )

        base_query = self._apply_common_scope_filters(
            base_query,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )

        rows = (
            base_query
            .group_by(User.id, User.nome, User.email, User.role, User.setor)
            .order_by(func.count(Scope.id).desc(), User.nome.asc())
            .all()
        )

        items: list[dict] = []

        for row in rows:
            item = {
                "userId": str(row.user_id),
                "userName": row.user_name,
                "userEmail": row.user_email,
                "userRole": row.user_role,
                "userSetor": row.user_setor,
                "totalScopes": int(row.total_scopes or 0),
            }

            if include_scopes:
                scope_query = (
                    db.session.query(Scope)
                    .outerjoin(Client, Scope.client_id == Client.id)
                    .filter(Scope.created_by_id == row.user_id)
                )

                scope_query = self._apply_common_scope_filters(
                    scope_query,
                    status=status,
                    date_from=date_from,
                    date_to=date_to,
                )

                scopes = (
                    scope_query
                    .order_by(Scope.created_at.desc().nullslast(), Scope.updated_at.desc().nullslast())
                    .limit(scopes_limit_per_user)
                    .all()
                )

                item["scopes"] = [
                    {
                        "id": str(scope.id),
                        "status": scope.status,
                        "clientId": str(scope.client_id) if scope.client_id else None,
                        "clientName": scope.client.razao_social if scope.client else None,
                        "clientCnpj": scope.client.cnpj if scope.client else None,
                        "responsibleUserId": str(scope.responsible_user_id) if scope.responsible_user_id else None,
                        "createdAt": self._dt(scope.created_at),
                        "updatedAt": self._dt(scope.updated_at),
                        "lastPublishedAt": self._dt(scope.last_published_at),
                    }
                    for scope in scopes
                ]

                item["scopesLimit"] = scopes_limit_per_user
                item["scopesTruncated"] = len(scopes) >= scopes_limit_per_user

            items.append(item)

        return {
            "items": items,
            "totalUsers": len(items),
            "totalScopes": sum(item["totalScopes"] for item in items),
        }

    def get_services_summary(
        self,
        *,
        status: str | None = None,
        operation_type: str | None = None,
        service_code: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict:
        """
        Retorna quais serviços estão sendo cadastrados/contratados,
        considerando apenas ScopeService.enabled == True.
        """

        query = (
            db.session.query(
                ServiceCatalog.id.label("service_catalog_id"),
                ServiceCatalog.code.label("service_code"),
                ServiceCatalog.nome.label("service_name"),
                ServiceCatalog.operation_type.label("operation_type"),
                ScopeService.currency.label("currency"),
                func.count(ScopeService.id).label("total_occurrences"),
                func.count(distinct(ScopeService.scope_id)).label("total_scopes"),
                func.sum(ScopeService.amount).label("total_amount"),
                func.avg(ScopeService.amount).label("average_amount"),
                func.min(ScopeService.amount).label("min_amount"),
                func.max(ScopeService.amount).label("max_amount"),
            )
            .join(ScopeService, ScopeService.service_catalog_id == ServiceCatalog.id)
            .join(Scope, Scope.id == ScopeService.scope_id)
            .filter(ScopeService.enabled.is_(True))
        )

        query = self._apply_common_scope_filters(
            query,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )

        if operation_type:
            query = query.filter(ServiceCatalog.operation_type == operation_type)

        if service_code:
            query = query.filter(
                or_(
                    ServiceCatalog.code == service_code,
                    ServiceCatalog.code.ilike(f"%:{service_code}"),
                )
            )

        rows = (
            query
            .group_by(
                ServiceCatalog.id,
                ServiceCatalog.code,
                ServiceCatalog.nome,
                ServiceCatalog.operation_type,
                ScopeService.currency,
            )
            .order_by(func.count(ScopeService.id).desc(), ServiceCatalog.nome.asc())
            .all()
        )

        items = [
            {
                "serviceCatalogId": str(row.service_catalog_id),
                "serviceCode": row.service_code,
                "serviceName": row.service_name,
                "operationType": row.operation_type,
                "currency": row.currency,
                "totalOccurrences": int(row.total_occurrences or 0),
                "totalScopes": int(row.total_scopes or 0),
                "totalAmount": self._money(row.total_amount) or 0,
                "averageAmount": self._money(row.average_amount),
                "minAmount": self._money(row.min_amount),
                "maxAmount": self._money(row.max_amount),
            }
            for row in rows
        ]

        return {
            "items": items,
            "totalServices": len(items),
            "totalOccurrences": sum(item["totalOccurrences"] for item in items),
            "totalAmount": sum(item["totalAmount"] for item in items),
        }

    def get_services_by_scope(
        self,
        *,
        status: str | None = None,
        operation_type: str | None = None,
        service_code: str | None = None,
        created_by_id: str | None = None,
        responsible_user_id: str | None = None,
        client_id: str | None = None,
        q: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """
        Lista serviços habilitados por escopo, com valores.
        Útil para tabela detalhada da interface.
        """

        limit, offset = self._pagination(limit, offset)

        query = (
            db.session.query(
                ScopeService.id.label("scope_service_id"),
                Scope.id.label("scope_id"),
                Scope.status.label("scope_status"),
                Scope.created_at.label("scope_created_at"),
                Scope.updated_at.label("scope_updated_at"),
                Scope.created_by_id.label("created_by_id"),
                User.nome.label("created_by_name"),
                Client.id.label("client_id"),
                Client.razao_social.label("client_name"),
                Client.cnpj.label("client_cnpj"),
                ServiceCatalog.id.label("service_catalog_id"),
                ServiceCatalog.code.label("service_code"),
                ServiceCatalog.nome.label("service_name"),
                ServiceCatalog.operation_type.label("operation_type"),
                ScopeService.pricing_type.label("pricing_type"),
                ScopeService.amount.label("amount"),
                ScopeService.currency.label("currency"),
                ScopeService.responsible_user_id.label("service_responsible_user_id"),
                ScopeService.extra_data.label("extra_data"),
            )
            .join(Scope, Scope.id == ScopeService.scope_id)
            .join(ServiceCatalog, ServiceCatalog.id == ScopeService.service_catalog_id)
            .outerjoin(Client, Client.id == Scope.client_id)
            .outerjoin(User, User.id == Scope.created_by_id)
            .filter(ScopeService.enabled.is_(True))
        )

        query = self._apply_common_scope_filters(
            query,
            status=status,
            created_by_id=created_by_id,
            responsible_user_id=responsible_user_id,
            client_id=client_id,
            date_from=date_from,
            date_to=date_to,
        )

        if operation_type:
            query = query.filter(ServiceCatalog.operation_type == operation_type)

        if service_code:
            query = query.filter(
                or_(
                    ServiceCatalog.code == service_code,
                    ServiceCatalog.code.ilike(f"%:{service_code}"),
                )
            )

        if q:
            term = f"%{q.strip()}%"
            query = query.filter(
                or_(
                    Client.razao_social.ilike(term),
                    Client.cnpj.ilike(term),
                    ServiceCatalog.nome.ilike(term),
                    ServiceCatalog.code.ilike(term),
                    Scope.status.ilike(term),
                )
            )

        total = query.count()

        rows = (
            query
            .order_by(Scope.updated_at.desc().nullslast(), Scope.created_at.desc().nullslast())
            .limit(limit)
            .offset(offset)
            .all()
        )

        items = [
            {
                "scopeServiceId": str(row.scope_service_id),
                "scopeId": str(row.scope_id),
                "scopeStatus": row.scope_status,
                "scopeCreatedAt": self._dt(row.scope_created_at),
                "scopeUpdatedAt": self._dt(row.scope_updated_at),
                "createdById": str(row.created_by_id) if row.created_by_id else None,
                "createdByName": row.created_by_name,
                "clientId": str(row.client_id) if row.client_id else None,
                "clientName": row.client_name,
                "clientCnpj": row.client_cnpj,
                "serviceCatalogId": str(row.service_catalog_id),
                "serviceCode": row.service_code,
                "serviceName": row.service_name,
                "operationType": row.operation_type,
                "pricingType": row.pricing_type,
                "amount": self._money(row.amount),
                "currency": row.currency,
                "serviceResponsibleUserId": (
                    str(row.service_responsible_user_id)
                    if row.service_responsible_user_id
                    else None
                ),
                "extraData": row.extra_data or {},
            }
            for row in rows
        ]

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_admin_metrics_overview(
        self,
        *,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict:
        """
        Resumo para cards principais do dashboard.
        """

        scope_query = self._apply_common_scope_filters(
            db.session.query(Scope),
            status=status,
            date_from=date_from,
            date_to=date_to,
        )

        service_query = (
            db.session.query(ScopeService)
            .join(Scope, Scope.id == ScopeService.scope_id)
            .filter(ScopeService.enabled.is_(True))
        )
        service_query = self._apply_common_scope_filters(
            service_query,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )

        amount_query = (
            db.session.query(func.sum(ScopeService.amount))
            .join(Scope, Scope.id == ScopeService.scope_id)
            .filter(ScopeService.enabled.is_(True))
        )
        amount_query = self._apply_common_scope_filters(
            amount_query,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )

        distinct_services_query = (
            db.session.query(func.count(distinct(ScopeService.service_catalog_id)))
            .join(Scope, Scope.id == ScopeService.scope_id)
            .filter(ScopeService.enabled.is_(True))
        )
        distinct_services_query = self._apply_common_scope_filters(
            distinct_services_query,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )

        return {
            "totalScopes": scope_query.count(),
            "totalEnabledServices": service_query.count(),
            "totalDistinctServices": int(distinct_services_query.scalar() or 0),
            "totalServicesAmount": self._money(amount_query.scalar()) or 0,
        }
