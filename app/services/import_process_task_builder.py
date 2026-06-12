from app.extensions import db
from app.models.process import (
    ImportProcess,
    ImportProcessTask,
    ImportProcessTaskChecklistItem,
)
from app.services.import_process_checklist_rules import (
    PROCESS_TASK_RULES,
    resolve_initial_task_status,
    resolve_task_service_type,
)


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def get_internal_service_values(process: ImportProcess) -> set[str]:
    return {
        _enum_value(service.service_type)
        for service in process.services
        if _enum_value(service.responsibility) == "internal"
        and _enum_value(service.status) != "cancelled"
    }


def create_tasks_for_process(
    process: ImportProcess,
    payload: dict,
) -> list[ImportProcessTask]:
    internal_services = get_internal_service_values(process)

    created_tasks = []

    for rule in PROCESS_TASK_RULES:
        service_type = resolve_task_service_type(
            task_key=rule.task_key,
            active_services=internal_services,
        )

        task_status = resolve_initial_task_status(
            task_key=rule.task_key,
            payload=payload,
        )

        task = ImportProcessTask(
            import_process_id=process.id,
            stage=rule.stage,
            service_type=service_type,
            task_key=rule.task_key,
            name=rule.name,
            status=task_status,
            position=rule.position,
        )

        db.session.add(task)
        db.session.flush()

        for item_position, item_rule in enumerate(rule.checklist_items, start=1):
            item = ImportProcessTaskChecklistItem(
                task_id=task.id,
                item_key=item_rule.item_key,
                label=item_rule.label,
                status=task_status,
                required=item_rule.required,
                position=item_position,
            )

            db.session.add(item)

        created_tasks.append(task)

    return created_tasks