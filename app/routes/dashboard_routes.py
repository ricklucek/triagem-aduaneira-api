from __future__ import annotations

from datetime import datetime

from flask import Blueprint, g, jsonify, request

from ..auth import admin_required, roles_required
from ..services.dashboard_metrics_service import DashboardMetricsService

dashboard_bp = Blueprint("dashboards", __name__, url_prefix="/dashboards")


def _parse_bool(value, default=False) -> bool:
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    value = str(value).strip().lower()
    return value in ("1", "true", "sim", "s", "yes", "y")


def _parse_int(value, default: int, min_value: int | None = None, max_value: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default

    if min_value is not None and parsed < min_value:
        parsed = min_value

    if max_value is not None and parsed > max_value:
        parsed = max_value

    return parsed


def _parse_datetime(value):
    """
    Aceita:
    - YYYY-MM-DD
    - YYYY-MM-DDTHH:MM:SS
    - ISO com Z
    """
    if not value:
        return None

    raw = str(value).strip()

    try:
        if len(raw) == 10:
            return datetime.fromisoformat(raw)

        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _common_filters() -> dict:
    return {
        "status": request.args.get("status") or None,
        "operation_type": request.args.get("operationType") or request.args.get("operation_type") or None,
        "service_code": request.args.get("serviceCode") or request.args.get("service_code") or None,
        "created_by_id": request.args.get("createdById") or request.args.get("created_by_id") or None,
        "responsible_user_id": request.args.get("responsibleUserId") or request.args.get("responsible_user_id") or None,
        "client_id": request.args.get("clientId") or request.args.get("client_id") or None,
        "q": request.args.get("q") or None,
        "date_from": _parse_datetime(request.args.get("dateFrom") or request.args.get("date_from")),
        "date_to": _parse_datetime(request.args.get("dateTo") or request.args.get("date_to")),
    }


@dashboard_bp.get("/admin")
@admin_required
def admin_dashboard():
    """
    Endpoint legado mantido para compatibilidade com o front atual.
    """
    service = DashboardMetricsService(g.current_user)
    filters = _common_filters()

    overview = service.get_admin_metrics_overview(
        status=filters["status"],
        date_from=filters["date_from"],
        date_to=filters["date_to"],
    )

    scopes_by_user = service.get_scopes_by_user(
        status=filters["status"],
        date_from=filters["date_from"],
        date_to=filters["date_to"],
        include_scopes=False,
    )

    return jsonify(
        {
            "createdLastMonth": 0,
            "outdatedScopes": 0,
            "scopesByPerson": [
                {
                    "group": item["userId"],
                    "name": item["userName"],
                    "total": item["totalScopes"],
                }
                for item in scopes_by_user["items"]
            ],
            "scopesBySector": [],
            "comercialAveragePrice": 0,
            "totalScopes": overview["totalScopes"],
            "totalEnabledServices": overview["totalEnabledServices"],
            "totalDistinctServices": overview["totalDistinctServices"],
            "totalServicesAmount": overview["totalServicesAmount"],
        }
    )


@dashboard_bp.get("/admin/metrics")
@admin_required
def admin_metrics_overview():
    service = DashboardMetricsService(g.current_user)
    filters = _common_filters()

    data = service.get_admin_metrics_overview(
        status=filters["status"],
        date_from=filters["date_from"],
        date_to=filters["date_to"],
    )

    return jsonify(data)


@dashboard_bp.get("/admin/scopes-by-user")
@admin_required
def admin_scopes_by_user():
    service = DashboardMetricsService(g.current_user)
    filters = _common_filters()

    include_scopes = _parse_bool(request.args.get("includeScopes"), default=True)
    scopes_limit_per_user = _parse_int(
        request.args.get("scopesLimitPerUser"),
        default=50,
        min_value=1,
        max_value=500,
    )

    data = service.get_scopes_by_user(
        status=filters["status"],
        date_from=filters["date_from"],
        date_to=filters["date_to"],
        include_scopes=include_scopes,
        scopes_limit_per_user=scopes_limit_per_user,
    )

    return jsonify(data)


@dashboard_bp.get("/admin/services")
@admin_required
def admin_services_summary():
    service = DashboardMetricsService(g.current_user)
    filters = _common_filters()

    data = service.get_services_summary(
        status=filters["status"],
        operation_type=filters["operation_type"],
        service_code=filters["service_code"],
        date_from=filters["date_from"],
        date_to=filters["date_to"],
    )

    return jsonify(data)


@dashboard_bp.get("/admin/services/by-scope")
@admin_required
def admin_services_by_scope():
    service = DashboardMetricsService(g.current_user)
    filters = _common_filters()

    limit = _parse_int(request.args.get("limit"), default=50, min_value=1, max_value=500)
    offset = _parse_int(request.args.get("offset"), default=0, min_value=0)

    data = service.get_services_by_scope(
        status=filters["status"],
        operation_type=filters["operation_type"],
        service_code=filters["service_code"],
        created_by_id=filters["created_by_id"],
        responsible_user_id=filters["responsible_user_id"],
        client_id=filters["client_id"],
        q=filters["q"],
        date_from=filters["date_from"],
        date_to=filters["date_to"],
        limit=limit,
        offset=offset,
    )

    return jsonify(data)


@dashboard_bp.get("/comercial")
@roles_required("comercial")
def comercial_dashboard():
    service = DashboardMetricsService(g.current_user)
    overview = service.get_admin_metrics_overview()
    return jsonify(
        {
            "responsibleScopes": 0,
            "salesAveragePrice": 0,
            "createdLastMonthAsResponsible": 0,
            "totalScopes": overview["totalScopes"],
            "totalEnabledServices": overview["totalEnabledServices"],
        }
    )


@dashboard_bp.get("/credenciamento")
@roles_required("credenciamento")
def credenciamento_dashboard():
    return jsonify(
        {
            "createdLastMonth": 0,
            "expiredScopes": 0,
            "createdByUser": 0,
            "waitingAdjustment": 0,
        }
    )


@dashboard_bp.get("/operacao")
@roles_required("operacao")
def operacao_dashboard():
    return jsonify(
        {
            "responsibleScopes": 0,
            "createdLastMonth": 0,
            "waitingAdjustment": 0,
        }
    )
