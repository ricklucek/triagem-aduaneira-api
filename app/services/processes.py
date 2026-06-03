from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from app.models import (
    ImportProcess,
    ImportProcessTag,
    Client
)


class ImportProcessService:
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

        total = query.distinct().count()

        rows = (
            query
            .distinct()
            .order_by(ImportProcess.opened_at.desc(), ImportProcess.id.desc())
            .limit(limit)
            .offset(offset)
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