from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_

from app.extensions import db
from app.models import FiscalMunicipality, NfeCarrier


class NfeCarrierAlreadyExistsError(ValueError):
    def __init__(self, existing_id):
        self.existing_id = existing_id
        super().__init__("Já existe uma transportadora com este CPF/CNPJ.")


class NfeCarrierService:
    def __init__(self, current_user):
        self.organization_id = getattr(current_user, "organization_id", None)

    def query(self):
        if not self.organization_id:
            raise ValueError("O usuário precisa estar vinculado a uma organização.")
        return NfeCarrier.query.filter(
            NfeCarrier.organization_id == self.organization_id
        )

    def list(self, *, query: str, active: bool | None, limit: int, offset: int):
        rows_query = self.query()
        if active is not None:
            rows_query = rows_query.filter(NfeCarrier.active.is_(active))
        term = (query or "").strip()
        if term:
            like = f"%{term}%"
            digits = "".join(character for character in term if character.isdigit())
            conditions = [
                NfeCarrier.legal_name.ilike(like),
                NfeCarrier.trade_name.ilike(like),
            ]
            if digits:
                conditions.append(NfeCarrier.tax_id.ilike(f"%{digits}%"))
            rows_query = rows_query.filter(or_(*conditions))

        total = rows_query.count()
        rows = (
            rows_query.order_by(
                NfeCarrier.active.desc(),
                NfeCarrier.legal_name.asc(),
            )
            .limit(limit)
            .offset(offset)
            .all()
        )
        return rows, total

    def get(self, carrier_id):
        return self.query().filter(NfeCarrier.id == carrier_id).first()

    def create(self, data: dict) -> NfeCarrier:
        self._ensure_unique_tax_id(data["tax_id"])
        municipality = self._municipality(data["municipality_code"])
        carrier = NfeCarrier(
            organization_id=self.organization_id,
            **self._model_data(data, municipality),
        )
        db.session.add(carrier)
        return carrier

    def update(self, carrier: NfeCarrier, data: dict) -> NfeCarrier:
        if "tax_id" in data and data["tax_id"] != carrier.tax_id:
            self._ensure_unique_tax_id(data["tax_id"], exclude_id=carrier.id)

        municipality = None
        if "municipality_code" in data:
            municipality = self._municipality(data["municipality_code"])
        for field, value in self._model_data(data, municipality).items():
            setattr(carrier, field, value)
        carrier.updated_at = datetime.utcnow()
        return carrier

    def snapshot(self, carrier: NfeCarrier) -> dict:
        address = ", ".join(
            part
            for part in (
                carrier.street,
                carrier.number,
                carrier.complement,
                carrier.district,
            )
            if part
        )
        return {
            "source_carrier_id": str(carrier.id),
            "tax_id": carrier.tax_id,
            "name": carrier.legal_name,
            "trade_name": carrier.trade_name,
            "state_registration": carrier.state_registration,
            "address": address,
            "street": carrier.street,
            "number": carrier.number,
            "complement": carrier.complement,
            "district": carrier.district,
            "municipality_code": carrier.municipality_code,
            "city_name": carrier.municipality_name,
            "state": carrier.state,
            "zip_code": carrier.zip_code,
            "phone": carrier.phone,
            "email": carrier.email,
        }

    def _municipality(self, code: str) -> FiscalMunicipality:
        municipality = FiscalMunicipality.query.filter(
            FiscalMunicipality.code == code,
            FiscalMunicipality.active.is_(True),
        ).first()
        if not municipality:
            raise ValueError(
                "Município não encontrado no catálogo fiscal ativo. "
                "Sincronize a referência do IBGE e selecione novamente."
            )
        return municipality

    def _ensure_unique_tax_id(self, tax_id: str, exclude_id=None) -> None:
        query = self.query().filter(NfeCarrier.tax_id == tax_id)
        if exclude_id:
            query = query.filter(NfeCarrier.id != exclude_id)
        existing = query.first()
        if existing:
            raise NfeCarrierAlreadyExistsError(existing.id)

    @staticmethod
    def _model_data(data: dict, municipality: FiscalMunicipality | None) -> dict:
        allowed = {
            "legal_name",
            "trade_name",
            "tax_id",
            "state_registration",
            "street",
            "number",
            "complement",
            "district",
            "municipality_code",
            "zip_code",
            "phone",
            "email",
            "active",
        }
        result = {key: value for key, value in data.items() if key in allowed}
        if municipality:
            result["municipality_code"] = municipality.code
            result["municipality_name"] = municipality.name
            result["state"] = municipality.state
        return result
