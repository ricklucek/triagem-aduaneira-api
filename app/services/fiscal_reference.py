from __future__ import annotations

from datetime import date
import unicodedata

from app.models.fiscal_reference import FiscalCountry, FiscalMunicipality


def _search_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").strip())
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


class FiscalReferenceService:
    """Consulta catálogos fiscais sem depender de extensões do PostgreSQL."""

    @staticmethod
    def search_municipalities(
        *,
        query: str = "",
        state: str | None = None,
        limit: int = 20,
    ) -> list[FiscalMunicipality]:
        rows_query = FiscalMunicipality.query.filter(
            FiscalMunicipality.active.is_(True)
        )
        normalized_state = (state or "").strip().upper()
        if normalized_state:
            rows_query = rows_query.filter(
                FiscalMunicipality.state == normalized_state
            )

        normalized_query = _search_text(query)
        rows = rows_query.order_by(
            FiscalMunicipality.name.asc(),
            FiscalMunicipality.state.asc(),
        ).all()
        if normalized_query:
            rows = [
                row
                for row in rows
                if normalized_query in _search_text(row.name)
                or normalized_query in row.code
            ]
        return rows[:limit]

    @staticmethod
    def search_countries(
        *,
        query: str = "",
        active_on: date,
        limit: int = 20,
    ) -> list[FiscalCountry]:
        rows = (
            FiscalCountry.query.filter(FiscalCountry.active.is_(True))
            .order_by(FiscalCountry.name.asc())
            .all()
        )
        normalized_query = _search_text(query)
        eligible = []
        for row in rows:
            if row.valid_from and row.valid_from > active_on:
                continue
            if row.valid_until and row.valid_until < active_on:
                continue
            if normalized_query and not any(
                normalized_query in value
                for value in (
                    _search_text(row.name),
                    _search_text(row.bacen_code),
                    _search_text(row.iso_alpha_2),
                    _search_text(row.iso_alpha_3),
                )
            ):
                continue
            eligible.append(row)
        return eligible[:limit]
