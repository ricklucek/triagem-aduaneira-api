from flask import Blueprint, jsonify, request
from marshmallow import ValidationError

from app.schemas.process import (
    ImportProcessListQuerySchema,
    ImportProcessSchema,
)
from app.services.processes import ImportProcessService


app = Blueprint(
    "import_processes",
    __name__,
    url_prefix="/tracker/import-processes",
)


@app.get("")
def list_import_processes():
    
    filters = request.args

    result = ImportProcessService.list_processes(
        search=filters.get("search"),
        stage=filters.get("stage"),
        client_id=filters.get("clientId"),
        tag=filters.get("tag"),
        limit=filters.get("limit", 50),
        offset=filters.get("offset", 0),
    )

    return jsonify(
        {
            "items": ImportProcessSchema(many=True).dump(result["items"]),
            "total": result["total"],
            "limit": result["limit"],
            "offset": result["offset"],
        }
    ), 200


@app.get("/<int:process_id>")
def get_import_process_by_id(process_id: int):
    process = ImportProcessService.get_process_by_id(process_id)

    if not process:
        return jsonify(
            {
                "message": "Import process not found.",
            }
        ), 404

    return jsonify(ImportProcessSchema().dump(process)), 200