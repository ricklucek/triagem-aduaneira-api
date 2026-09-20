from app.schemas.preposto import PrepostoLookupItemSchema


def test_lookup_item_exposes_locality_type():
    payload = {
        "id": "preposto-1",
        "localidadeId": "localidade-1",
        "nome": "Preposto Teste",
        "cidade": "Santos",
        "uf": "SP",
        "descricaoLocal": "Porto de Santos",
        "tipoLocal": "PORTO",
        "operacao": "EXPORTACAO",
        "valor": None,
        "valorDescricao": None,
        "moeda": "BRL",
        "telefone": None,
        "email": None,
        "contatoNome": None,
        "observacoes": None,
        "tarifas": [],
        "credenciados": [],
    }

    assert PrepostoLookupItemSchema().dump(payload)["tipoLocal"] == "PORTO"
