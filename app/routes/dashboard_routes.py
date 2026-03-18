from datetime import datetime, timedelta

from flask import Blueprint, jsonify
from sqlalchemy import func

from ..auth import admin_required, roles_required
from ..models import Scope

dashboard_bp = Blueprint("dashboards", __name__, url_prefix="/dashboards")


@dashboard_bp.get("/admin")
@admin_required
def admin_dashboard():
    month_ago = datetime.utcnow() - timedelta(days=30)
    created_last_month = Scope.query.filter(Scope.updated_at >= month_ago).count()
    outdated = Scope.query.filter(Scope.status == "draft").count()
    total = Scope.query.count()

    by_person = (
        Scope.query.with_entities(Scope.created_by_id.label("group"), func.count(Scope.id).label("total"))
        .group_by(Scope.created_by_id)
        .all()
    )

    return jsonify(
        {
            "createdLastMonth": created_last_month,
            "outdatedScopes": outdated,
            "scopesByPerson": [{"group": item.group, "total": item.total} for item in by_person],
            "scopesBySector": [],
            "comercialAveragePrice": 0,
            "totalScopes": total,
        }
    )


@dashboard_bp.get("/comercial")
@roles_required("comercial")
def comercial_dashboard():
    return jsonify({"responsibleScopes": 0, "salesAveragePrice": 0, "createdLastMonthAsResponsible": 0})


@dashboard_bp.get("/credenciamento")
@roles_required("credenciamento")
def credenciamento_dashboard():
    return jsonify({"createdLastMonth": 0, "expiredScopes": 0, "createdByUser": 0, "waitingAdjustment": 0})


@dashboard_bp.get("/operacao")
@roles_required("operacao")
def operacao_dashboard():
    return jsonify({"responsibleScopes": 0, "createdLastMonth": 0, "waitingAdjustment": 0})
