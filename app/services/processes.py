from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import (
    Client,
    ImportProcess,
    ImportProcessShipment,
    ImportProcessFreight,
    ImportProcessService as ImportProcessServiceModel,
    ImportProcessTag,
)


class ImportProcessService:

    @staticmethod
    def create_import_process(payload: dict) -> ImportProcess:
        client_id = payload["client_id"]

        client = Client.query.filter(Client.id == client_id).first()

        if not client:
            raise ValueError("Client not found.")

        process_number = payload["process_number"]

        existing_process = (
            ImportProcess.query
            .filter(ImportProcess.process_number == process_number)
            .first()
        )

        if existing_process:
            raise ValueError("An import process with this process_number already exists.")

        process = ImportProcess(
            process_number=payload["process_number"],
            internal_reference=payload.get("internal_reference"),
            client_reference=payload.get("client_reference"),
            client_id=payload["client_id"],
            opened_at=payload["opened_at"],
            current_stage=payload.get("current_stage", "pre_shipment"),
            metadata_json=payload.get("metadata_json"),
            notes=payload.get("notes"),
        )

        shipment_payload = payload.get("shipment")

        if shipment_payload:
            has_shipment_data = any(
                shipment_payload.get(field)
                for field in (
                    "estimated_departure_at",
                    "estimated_arrival_at",
                    "actual_departure_at",
                    "actual_arrival_at",
                    "origin",
                    "destination",
                    "vessel_name",
                    "voyage_number",
                    "master_bl",
                    "house_bl",
                    "container_number",
                    "notes",
                )
            )

            if has_shipment_data:
                process.shipments.append(
                    ImportProcessShipment(
                        estimated_departure_at=shipment_payload.get(
                            "estimated_departure_at"
                        ),
                        estimated_arrival_at=shipment_payload.get(
                            "estimated_arrival_at"
                        ),
                        actual_departure_at=shipment_payload.get(
                            "actual_departure_at"
                        ),
                        actual_arrival_at=shipment_payload.get(
                            "actual_arrival_at"
                        ),
                        origin=shipment_payload.get("origin"),
                        destination=shipment_payload.get("destination"),
                        vessel_name=shipment_payload.get("vessel_name"),
                        voyage_number=shipment_payload.get("voyage_number"),
                        master_bl=shipment_payload.get("master_bl"),
                        house_bl=shipment_payload.get("house_bl"),
                        container_number=shipment_payload.get("container_number"),
                        notes=shipment_payload.get("notes"),
                    )
                )

        freight_payload = payload.get("freight")

        if freight_payload:
            process.freight = ImportProcessFreight(
                international_freight_responsibility=freight_payload.get(
                    "international_freight_responsibility",
                    "not_applicable",
                ),
                quote_status=freight_payload.get(
                    "quote_status",
                    "not_requested",
                ),
                provider_name=freight_payload.get("provider_name"),
                quoted_amount=freight_payload.get("quoted_amount"),
                quoted_currency=freight_payload.get("quoted_currency"),
                quote_requested_at=freight_payload.get("quote_requested_at"),
                quote_approved_at=freight_payload.get("quote_approved_at"),
                quote_rejected_at=freight_payload.get("quote_rejected_at"),
                notes=freight_payload.get("notes"),
            )

            if (
                process.freight.quote_status == "approved"
                and not process.freight.quote_approved_at
            ):
                process.freight.quote_approved_at = datetime.utcnow()

            if (
                process.freight.quote_status == "rejected"
                and not process.freight.quote_rejected_at
            ):
                process.freight.quote_rejected_at = datetime.utcnow()

        else:
            process.freight = ImportProcessFreight(
                international_freight_responsibility="not_applicable",
                quote_status="not_requested",
            )

        services_payload = payload.get("services") or []

        for service_payload in services_payload:
            process.services.append(
                ImportProcessServiceModel(
                    service_type=service_payload["service_type"],
                    status=service_payload.get("status", "pending"),
                    started_at=service_payload.get("started_at"),
                    completed_at=service_payload.get("completed_at"),
                    cancelled_at=service_payload.get("cancelled_at"),
                    notes=service_payload.get("notes"),
                )
            )

        tags_payload = payload.get("tags") or []

        for tag_payload in tags_payload:
            process.tags.append(
                ImportProcessTag(
                    tag_type=tag_payload["tag_type"],
                )
            )

        db.session.add(process)
        db.session.commit()

        created_process = (
            ImportProcess.query
            .options(
                selectinload(ImportProcess.client),
                selectinload(ImportProcess.shipments),
                selectinload(ImportProcess.freight),
                selectinload(ImportProcess.services),
                selectinload(ImportProcess.tasks),
                selectinload(ImportProcess.tags),
            )
            .filter(ImportProcess.id == process.id)
            .first()
        )

        return created_process

    @staticmethod
    def list_processes(
        *,
        search: str | None = None,
        stage: str | None = None,
        client_id: int | None = None,
        tag: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        query = (
            ImportProcess.query
            .options(
                selectinload(ImportProcess.client),
                selectinload(ImportProcess.shipments),
                selectinload(ImportProcess.freight),
                selectinload(ImportProcess.services),
                selectinload(ImportProcess.tasks),
                selectinload(ImportProcess.tags),
            )
        )

        if search:
            normalized_search = f"%{search.strip()}%"

            query = (
                query
                .join(Client, Client.id == ImportProcess.client_id)
                .filter(
                    or_(
                        ImportProcess.process_number.ilike(normalized_search),
                        ImportProcess.internal_reference.ilike(normalized_search),
                        ImportProcess.client_reference.ilike(normalized_search),
                        Client.razao_social.ilike(normalized_search),
                        Client.nome_resumido.ilike(normalized_search),
                    )
                )
            )

        if stage:
            query = query.filter(ImportProcess.current_stage == stage)

        if client_id:
            query = query.filter(ImportProcess.client_id == client_id)

        if tag:
            query = (
                query
                .join(ImportProcessTag, ImportProcessTag.import_process_id == ImportProcess.id)
                .filter(ImportProcessTag.tag_type == tag)
            )

        total = query.count()

        rows = (
            query
            .order_by(ImportProcess.opened_at.desc(), ImportProcess.id.desc())
            .limit(int(limit))
            .offset(int(offset))
            .all()
        )

        return {
            "items": rows,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    def get_process_by_id(process_id: int):
        return (
            ImportProcess.query
            .options(
                selectinload(ImportProcess.client),
                selectinload(ImportProcess.shipments),
                selectinload(ImportProcess.freight),
                selectinload(ImportProcess.services),
                selectinload(ImportProcess.tasks),
                selectinload(ImportProcess.tags),
            )
            .filter(ImportProcess.id == process_id)
            .first()
        )