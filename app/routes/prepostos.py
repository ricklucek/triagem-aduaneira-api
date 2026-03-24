from flask import Blueprint, jsonify, request
from marshmallow import ValidationError
from sqlalchemy import and_, func

from app.extensions import db
from app.models import Preposto, PrepostoContato, PrepostoLocalidade
from app.schemas import (
    PrepostoSchema,
    PrepostoCreateSchema,
    PrepostoUpdateSchema,
    PrepostoContatoSchema,
    PrepostoContatoCreateSchema,
    PrepostoContatoUpdateSchema,
    PrepostoLocalidadeSchema,
    PrepostoLocalidadeCreateSchema,
    PrepostoLocalidadeUpdateSchema,
    PrepostoLookupResponseSchema,
)

prepostos_bp = Blueprint("prepostos", __name__, url_prefix="/prepostos")

def json_error(message: str, status_code: int = 400, errors=None):
    payload = {"message": message}
    if errors is not None:
        payload["errors"] = errors
    return jsonify(payload), status_code


def get_preposto_or_404(preposto_id: str):
    preposto = Preposto.query.get(preposto_id)
    if not preposto:
        return None
    return preposto


def get_contato_or_404(preposto_id: str, contato_id: str):
    contato = PrepostoContato.query.filter_by(id=contato_id, preposto_id=preposto_id).first()
    if not contato:
        return None
    return contato


def get_localidade_or_404(preposto_id: str, localidade_id: str):
    localidade = PrepostoLocalidade.query.filter_by(
        id=localidade_id,
        preposto_id=preposto_id,
    ).first()
    if not localidade:
        return None
    return localidade


def clear_other_principais(preposto_id, contato_id=None):
    q = PrepostoContato.query.filter_by(preposto_id=preposto_id, principal=True)
    if contato_id:
        q = q.filter(PrepostoContato.id != contato_id)

    for contato in q.all():
        contato.principal = False


@prepostos_bp.post("")
def create_preposto():
    try:
        payload = PrepostoCreateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return json_error("Dados inválidos para criação do preposto.", 422, err.messages)

    preposto = Preposto(
        nome=payload["nome"].strip(),
        razao_social=payload.get("razao_social"),
        ativo=payload.get("ativo", True),
        observacoes=payload.get("observacoes"),
    )

    db.session.add(preposto)
    db.session.commit()

    return jsonify(PrepostoSchema().dump(preposto)), 201


@prepostos_bp.get("")
def list_prepostos():
    nome = request.args.get("nome", "").strip()
    ativo = request.args.get("ativo")

    q = Preposto.query

    if nome:
        q = q.filter(Preposto.nome.ilike(f"%{nome}%"))

    if ativo is not None:
        ativo_bool = ativo.lower() in ("1", "true", "t", "sim", "yes")
        q = q.filter(Preposto.ativo.is_(ativo_bool))

    rows = q.order_by(Preposto.nome.asc()).all()

    return jsonify(
        {
            "items": PrepostoSchema(many=True).dump(rows),
            "total": len(rows),
        }
    ), 200


@prepostos_bp.get("/<uuid:preposto_id>")
def get_preposto(preposto_id):
    preposto = get_preposto_or_404(str(preposto_id))
    if not preposto:
        return json_error("Preposto não encontrado.", 404)

    return jsonify(PrepostoSchema().dump(preposto)), 200


@prepostos_bp.patch("/<uuid:preposto_id>")
def update_preposto(preposto_id):
    preposto = get_preposto_or_404(str(preposto_id))
    if not preposto:
        return json_error("Preposto não encontrado.", 404)

    try:
        payload = PrepostoUpdateSchema().load(request.get_json() or {}, partial=True)
    except ValidationError as err:
        return json_error("Dados inválidos para atualização do preposto.", 422, err.messages)

    if "nome" in payload:
        preposto.nome = payload["nome"].strip()

    if "razao_social" in payload:
        preposto.razao_social = payload["razao_social"]

    if "ativo" in payload:
        preposto.ativo = payload["ativo"]

    if "observacoes" in payload:
        preposto.observacoes = payload["observacoes"]

    db.session.commit()

    return jsonify(PrepostoSchema().dump(preposto)), 200


@prepostos_bp.delete("/<uuid:preposto_id>")
def delete_preposto(preposto_id):
    preposto = get_preposto_or_404(str(preposto_id))
    if not preposto:
        return json_error("Preposto não encontrado.", 404)

    db.session.delete(preposto)
    db.session.commit()

    return jsonify({"message": "Preposto excluído com sucesso."}), 200


@prepostos_bp.post("/<uuid:preposto_id>/contatos")
def create_preposto_contato(preposto_id):
    preposto = get_preposto_or_404(str(preposto_id))
    if not preposto:
        return json_error("Preposto não encontrado.", 404)

    try:
        payload = PrepostoContatoCreateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return json_error("Dados inválidos para criação do contato.", 422, err.messages)

    contato = PrepostoContato(
        preposto_id=preposto.id,
        nome=payload["nome"].strip(),
        email=payload.get("email"),
        telefone=payload.get("telefone"),
        whatsapp=payload.get("whatsapp"),
        principal=payload.get("principal", False),
    )

    db.session.add(contato)
    db.session.flush()

    if contato.principal:
        clear_other_principais(preposto.id, contato.id)

    db.session.commit()

    return jsonify(PrepostoContatoSchema().dump(contato)), 201


@prepostos_bp.patch("/<uuid:preposto_id>/contatos/<uuid:contato_id>")
def update_preposto_contato(preposto_id, contato_id):
    preposto = get_preposto_or_404(str(preposto_id))
    if not preposto:
        return json_error("Preposto não encontrado.", 404)

    contato = get_contato_or_404(str(preposto_id), str(contato_id))
    if not contato:
        return json_error("Contato não encontrado para este preposto.", 404)

    try:
        payload = PrepostoContatoUpdateSchema().load(request.get_json() or {}, partial=True)
    except ValidationError as err:
        return json_error("Dados inválidos para atualização do contato.", 422, err.messages)

    if "nome" in payload:
        contato.nome = payload["nome"].strip()

    if "email" in payload:
        contato.email = payload["email"]

    if "telefone" in payload:
        contato.telefone = payload["telefone"]

    if "whatsapp" in payload:
        contato.whatsapp = payload["whatsapp"]

    if "principal" in payload:
        contato.principal = payload["principal"]
        if contato.principal:
            clear_other_principais(preposto.id, contato.id)

    db.session.commit()

    return jsonify(PrepostoContatoSchema().dump(contato)), 200


@prepostos_bp.delete("/<uuid:preposto_id>/contatos/<uuid:contato_id>")
def delete_preposto_contato(preposto_id, contato_id):
    preposto = get_preposto_or_404(str(preposto_id))
    if not preposto:
        return json_error("Preposto não encontrado.", 404)

    contato = get_contato_or_404(str(preposto_id), str(contato_id))
    if not contato:
        return json_error("Contato não encontrado para este preposto.", 404)

    db.session.delete(contato)
    db.session.commit()

    return jsonify({"message": "Contato excluído com sucesso."}), 200


@prepostos_bp.post("/<uuid:preposto_id>/localidades")
def create_preposto_localidade(preposto_id):
    preposto = get_preposto_or_404(str(preposto_id))
    if not preposto:
        return json_error("Preposto não encontrado.", 404)

    try:
        payload = PrepostoLocalidadeCreateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return json_error("Dados inválidos para criação da localidade.", 422, err.messages)

    localidade = PrepostoLocalidade(
        preposto_id=preposto.id,
        cidade=payload["cidade"].strip(),
        uf=payload.get("uf"),
        descricao_local=payload.get("descricao_local"),
        tipo_local=payload.get("tipo_local"),
        atende_importacao=payload.get("atende_importacao", False),
        atende_exportacao=payload.get("atende_exportacao", False),
        valor_importacao=payload.get("valor_importacao"),
        valor_exportacao=payload.get("valor_exportacao"),
        valor_importacao_descricao=payload.get("valor_importacao_descricao"),
        valor_exportacao_descricao=payload.get("valor_exportacao_descricao"),
        moeda=payload.get("moeda", "BRL"),
        observacoes=payload.get("observacoes"),
    )

    db.session.add(localidade)
    db.session.commit()

    return jsonify(PrepostoLocalidadeSchema().dump(localidade)), 201


@prepostos_bp.patch("/<uuid:preposto_id>/localidades/<uuid:localidade_id>")
def update_preposto_localidade(preposto_id, localidade_id):
    preposto = get_preposto_or_404(str(preposto_id))
    if not preposto:
        return json_error("Preposto não encontrado.", 404)

    localidade = get_localidade_or_404(str(preposto_id), str(localidade_id))
    if not localidade:
        return json_error("Localidade não encontrada para este preposto.", 404)

    try:
        payload = PrepostoLocalidadeUpdateSchema().load(request.get_json() or {}, partial=True)
    except ValidationError as err:
        return json_error("Dados inválidos para atualização da localidade.", 422, err.messages)

    for field in [
        "cidade",
        "uf",
        "descricao_local",
        "tipo_local",
        "atende_importacao",
        "atende_exportacao",
        "valor_importacao",
        "valor_exportacao",
        "valor_importacao_descricao",
        "valor_exportacao_descricao",
        "moeda",
        "observacoes",
    ]:
        if field in payload:
            setattr(localidade, field, payload[field].strip() if field == "cidade" and payload[field] else payload[field])

    if not localidade.atende_importacao and not localidade.atende_exportacao:
        return json_error(
            "A localidade deve atender importação e/ou exportação.",
            422,
        )

    db.session.commit()

    return jsonify(PrepostoLocalidadeSchema().dump(localidade)), 200


@prepostos_bp.delete("/<uuid:preposto_id>/localidades/<uuid:localidade_id>")
def delete_preposto_localidade(preposto_id, localidade_id):
    preposto = get_preposto_or_404(str(preposto_id))
    if not preposto:
        return json_error("Preposto não encontrado.", 404)

    localidade = get_localidade_or_404(str(preposto_id), str(localidade_id))
    if not localidade:
        return json_error("Localidade não encontrada para este preposto.", 404)

    db.session.delete(localidade)
    db.session.commit()

    return jsonify({"message": "Localidade excluída com sucesso."}), 200


@prepostos_bp.get("/public/lookup")
def lookup_prepostos():
    params = request.args

    cidade = params.get("cidade", "").strip()
    operacao = params.get("operacao")

    principal_contact_subquery = (
        db.session.query(
            PrepostoContato.id.label("contato_id"),
            PrepostoContato.preposto_id.label("preposto_id"),
            func.row_number()
            .over(
                partition_by=PrepostoContato.preposto_id,
                order_by=PrepostoContato.created_at.asc(),
            )
            .label("rn"),
        )
        .filter(PrepostoContato.principal.is_(True))
        .subquery()
    )

    q = (
        db.session.query(
            Preposto.id.label("id"),
            Preposto.nome.label("nome"),
            PrepostoLocalidade.cidade.label("cidade"),
            PrepostoLocalidade.uf.label("uf"),
            PrepostoLocalidade.descricao_local.label("descricao_local"),
            PrepostoLocalidade.moeda.label("moeda"),
            PrepostoLocalidade.observacoes.label("observacoes"),
            PrepostoLocalidade.valor_importacao.label("valor_importacao"),
            PrepostoLocalidade.valor_exportacao.label("valor_exportacao"),
            PrepostoLocalidade.valor_importacao_descricao.label("valor_importacao_descricao"),
            PrepostoLocalidade.valor_exportacao_descricao.label("valor_exportacao_descricao"),
            PrepostoContato.nome.label("contato_nome"),
            PrepostoContato.email.label("email"),
            PrepostoContato.telefone.label("telefone"),
        )
        .join(PrepostoLocalidade, PrepostoLocalidade.preposto_id == Preposto.id)
        .outerjoin(
            principal_contact_subquery,
            and_(
                principal_contact_subquery.c.preposto_id == Preposto.id,
                principal_contact_subquery.c.rn == 1,
            ),
        )
        .outerjoin(
            PrepostoContato,
            PrepostoContato.id == principal_contact_subquery.c.contato_id,
        )
        .filter(Preposto.ativo.is_(True))
    )

    if cidade:
        q = q.filter(func.lower(PrepostoLocalidade.cidade) == cidade.lower())

    if operacao == "IMPORTACAO":
        q = q.filter(PrepostoLocalidade.atende_importacao.is_(True))
    elif operacao == "EXPORTACAO":
        q = q.filter(PrepostoLocalidade.atende_exportacao.is_(True))

    rows = q.order_by(Preposto.nome.asc()).all()

    items = []
    for row in rows:
        if operacao == "IMPORTACAO":
            valor = row.valor_importacao
            valor_descricao = row.valor_importacao_descricao
        else:
            valor = row.valor_exportacao
            valor_descricao = row.valor_exportacao_descricao

        items.append(
            {
                "id": str(row.id),
                "nome": row.nome,
                "cidade": row.cidade,
                "uf": row.uf,
                "descricaoLocal": row.descricao_local,
                "operacao": operacao,
                "valor": float(valor) if valor is not None else None,
                "valorDescricao": valor_descricao,
                "moeda": row.moeda or "BRL",
                "telefone": row.telefone,
                "email": row.email,
                "contatoNome": row.contato_nome,
                "observacoes": row.observacoes,
            }
        )

    payload = {
        "items": items,
        "total": len(items),
    }

    return jsonify(PrepostoLookupResponseSchema().dump(payload)), 200