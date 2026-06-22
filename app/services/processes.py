from datetime import datetime

from sqlalchemy import or_, func
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
from app.models.process import ImportProcessTask
from app.services.import_process_task_builder import create_tasks_for_process

DEPARTMENT_LABELS = {
    "customs_clearance": "Despacho Aduaneiro",
    "international_freight": "Frete Internacional",
    "international_insurance": "Seguro Internacional",
    "road_freight": "Frete Rodoviário",
    "financial": "Financeiro",
}


DEPARTMENT_BOARD_COLUMNS = {
    # Conforme o rastreador principal e a visão do Despacho Aduaneiro
    "customs_clearance": [
        {
            "key": "pre_shipment",
            "label": "Pré Embarque",
            "type": "stage",
        },
        {
            "key": "shipment_in_transit",
            "label": "Embarque e Trânsito",
            "type": "stage",
        },
        {
            "key": "customs_clearance",
            "label": "Chegada e Alfândega",
            "type": "stage",
        },
        {
            "key": "released_for_delivery",
            "label": "Liberação e Entrega",
            "type": "stage",
        },
    ],

    # Conforme fluxo do Lovable para FI
    "international_freight": [
        {
            "key": "abertura_processo",
            "label": "Abertura de Processo",
            "type": "task_key",
        },
        {
            "key": "booking",
            "label": "Booking",
            "type": "task_key",
        },
        {
            "key": "confirmacao_embarque",
            "label": "Confirmação de Embarque",
            "type": "task_key",
        },
        {
            "key": "follow_agente",
            "label": "Follow Agente",
            "type": "task_key",
        },
        {
            "key": "recebimento_bl",
            "label": "Recebimento BL",
            "type": "task_key",
        },
        {
            "key": "confirmacao_atracacao",
            "label": "Confirmação de Atracação",
            "type": "task_key",
        },
        {
            "key": "presenca_carga",
            "label": "Presença de Carga",
            "type": "task_key",
        },
        {
            "key": "pagamento_taxas_fi",
            "label": "Pagamento Taxas FI",
            "type": "task_key",
        },
    ],

    # Conforme fluxo do Lovable para seguro
    "international_insurance": [
        {
            "key": "averbar_seguro",
            "label": "Averbar Seguro",
            "type": "task_key",
        },
        {
            "key": "verificar_avarias",
            "label": "Verificar Avarias",
            "type": "task_key",
        },
    ],

    # Conforme fluxo do Lovable para Frete Rodoviário
    "road_freight": [
        {
            "key": "recebimento_agendamento",
            "label": "Recebimento / Agendamento",
            "type": "task_key",
        },
        {
            "key": "coleta",
            "label": "Coleta",
            "type": "task_key",
        },
        {
            "key": "entrega",
            "label": "Entrega",
            "type": "task_key",
        },
        {
            "key": "devolucao_container",
            "label": "Devolução Container",
            "type": "task_key",
        },
        {
            "key": "finalizacao_processo",
            "label": "Finalização do Processo",
            "type": "task_key",
        },
    ],

    # Conforme fluxo do Lovable para financeiro
    "financial": [
        {
            "key": "em_processo_faturamento",
            "label": "Em Processo de Faturamento",
            "type": "task_key",
        },
        {
            "key": "faturado",
            "label": "Faturado",
            "type": "task_key",
        },
        {
            "key": "processo_encerrado",
            "label": "Processo Encerrado",
            "type": "task_key",
        },
    ],
}

# Mapeia algumas task_keys atuais do backend para colunas do Lovable.
# Isso permite a API funcionar agora, mesmo antes de renomearmos todas as task_keys.
DEPARTMENT_TASK_COLUMN_ALIASES = {
    "road_freight": {
        "contactar_transportadora": "recebimento_agendamento",
        "agendamento_carregamento": "recebimento_agendamento",
        "formalizar_entrega": "entrega",
        "devolucao_container": "devolucao_container",
    },
    "financial": {},
    "international_freight": {},
    "international_insurance": {},
    "customs_clearance": {},
}

def normalize_services_payload(services_payload: list[dict]) -> list[dict]:
    normalized_by_type = {
        item["service_type"]: dict(item)
        for item in services_payload
    }

    normalized_by_type["customs_clearance"] = {
        **normalized_by_type.get("customs_clearance", {}),
        "service_type": "customs_clearance",
        "responsibility": "internal",
        "status": normalized_by_type.get("customs_clearance", {}).get("status", "pending"),
    }

    normalized_by_type["financial"] = {
        **normalized_by_type.get("financial", {}),
        "service_type": "financial",
        "responsibility": "internal",
        "status": normalized_by_type.get("financial", {}).get("status", "pending"),
    }

    return list(normalized_by_type.values())


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
            metadata_json=payload.get("metadata_json") or {},
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

        services_payload = normalize_services_payload(payload.get("services") or [])

        for service_payload in services_payload:
            process.services.append(
                ImportProcessServiceModel(
                    service_type=service_payload["service_type"],
                    responsibility=service_payload.get("responsibility", "internal"),
                    responsible_name=service_payload.get("responsible_name"),
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
        db.session.flush()

        create_tasks_for_process(process, payload)

        db.session.commit()

        created_process = (
            ImportProcess.query
            .options(
                selectinload(ImportProcess.client),
                selectinload(ImportProcess.shipments),
                selectinload(ImportProcess.freight),
                selectinload(ImportProcess.services),
                selectinload(ImportProcess.tasks).selectinload(ImportProcessTask.checklist_items),
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
                selectinload(ImportProcess.tasks).selectinload(ImportProcessTask.checklist_items),
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
                selectinload(ImportProcess.tasks).selectinload(ImportProcessTask.checklist_items),
                selectinload(ImportProcess.tags),
            )
            .filter(ImportProcess.id == process_id)
            .first()
        )
    
    @staticmethod
    def list_department_board(
        *,
        department: str,
        search: str | None = None,
        tag: str | None = None,
        include_completed: bool = False,
        limit: int = 100,
        offset: int = 0,
    ):
        if department not in DEPARTMENT_BOARD_COLUMNS:
            raise ValueError("Invalid department.")

        limit = int(limit)
        offset = int(offset)

        process_ids_query = (
            db.session.query(ImportProcess.id)
            .join(
                ImportProcessTask,
                ImportProcessTask.import_process_id == ImportProcess.id,
            )
            .filter(ImportProcessTask.service_type == department)
        )

        if not include_completed:
            process_ids_query = process_ids_query.filter(
                ImportProcessTask.status != "done"
            )

        if search:
            normalized_search = f"%{search.strip()}%"

            process_ids_query = (
                process_ids_query
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

        if tag:
            process_ids_query = (
                process_ids_query
                .join(
                    ImportProcessTag,
                    ImportProcessTag.import_process_id == ImportProcess.id,
                )
                .filter(ImportProcessTag.tag_type == tag)
            )

        process_ids_subquery = (
            process_ids_query
            .group_by(ImportProcess.id)
            .subquery()
        )

        total = (
            db.session.query(func.count())
            .select_from(process_ids_subquery)
            .scalar()
        )

        paginated_ids = [
            row.id
            for row in (
                db.session.query(process_ids_subquery.c.id)
                .join(
                    ImportProcess,
                    ImportProcess.id == process_ids_subquery.c.id,
                )
                .order_by(
                    ImportProcess.opened_at.desc(),
                    ImportProcess.id.desc(),
                )
                .limit(limit)
                .offset(offset)
                .all()
            )
        ]

        processes = (
            ImportProcess.query
            .filter(ImportProcess.id.in_(paginated_ids))
            .all()
        )

        return {
            "items": processes,
            "total": total,
            "limit": limit,
            "offset": offset,
        }