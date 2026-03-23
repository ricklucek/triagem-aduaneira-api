from copy import deepcopy
from copy import deepcopy

_DEFAULT_BANK_ACCOUNT = {"banco": "", "agencia": "", "conta": ""}
_DEFAULT_BENEFICIO = {"regime": "INTEGRAL", "detalheBeneficio": ""}

_DEFAULT_AFRMM = {
    "contaPagamento": "CASCO",
    "dadosContaCliente": deepcopy(_DEFAULT_BANK_ACCOUNT),
    "regime": "INTEGRAL",
    "detalheBeneficio": "",
}

_DEFAULT_ICMS = {
    "contaPagamento": "CASCO",
    "dadosContaCliente": deepcopy(_DEFAULT_BANK_ACCOUNT),
    "regime": "INTEGRAL",
    "recolhida": "",
    "efetiva": "",
}

_DEFAULT_SERVICO_VALOR_OU_SALARIO = {
    "habilitado": False,
    "tipoValor": None,
    "valor": None,
    "responsavel": None,
    "ultimaAtualizacao": None,
}

_DEFAULT_SERVICO_VALOR_SIMPLES = {
    "habilitado": False,
    "valor": None,
}

_DEFAULT_SERVICO_PREPOSTO = {
    "habilitado": False,
    "valor": None,
    "inclusoNoDesembaracoCasco": None,
    "cidadesLiberacao": [],
    "outroPorto": None,
    "outraFronteira": None,
    "prepostoSelecionado": None,
}

_DEFAULT_SERVICO_FRETE_INTERNACIONAL = {
    "habilitado": False,
    "ptaxNegociado": None,
}

_DEFAULT_SERVICO_SEGURO = {
    "habilitado": False,
    "valorMinimo": None,
    "percentualSobreCfr": None,
    "dataInclusaoApolice": None,
    "descricaoComplementar": None,
}

_DEFAULT_SERVICO_FRETE_RODOVIARIO = {
    "habilitado": False,
    "modalidade": None,
    "observacaoGeral": None,
}


DEFAULT_SCOPE_DRAFT = {
    "informacoesFixas": {
        "salarioMinimoVigente": 0,
        "dadosBancariosCasco": deepcopy(_DEFAULT_BANK_ACCOUNT),
    },
    "sobreEmpresa": {
        "razaoSocial": "",
        "cnpj": "",
        "inscricaoEstadual": "",
        "inscricaoMunicipal": "",
        "enderecoCompletoEscritorio": "",
        "enderecoCompletoArmazem": "",
        "cnaePrincipal": "",
        "cnaeSecundario": "",
        "regimeTributacao": "",
        "responsavelComercial": "",
    },
    "contatos": [
        {
            "nome": "",
            "cargoDepartamento": "",
            "email": "",
            "telefone": "",
        }
    ],
    "operacao": {
        "tipos": [],
        "importacao": {
            "analistaDA": "",
            "analistaAE": "",
            "produtosImportados": "",
            "ncms": [],
            "vinculoComExportador": "NAO",
            "locaisDesembaraco": [],
            "outroLocalDesembaraco": "",
            "locaisDespacho": [],
            "outroLocalDespacho": "",
            "necessidadeDtcDta": "NAO",
            "necessidadeLiLpco": "NAO",
            "anuencias": [],
            "outroOrgaoAnuente": "",
            "impostosFederais": {
                "contaPagamento": "CASCO",
                "dadosContaCliente": deepcopy(_DEFAULT_BANK_ACCOUNT),
                "ii": deepcopy(_DEFAULT_BENEFICIO),
                "ipi": deepcopy(_DEFAULT_BENEFICIO),
                "pis": deepcopy(_DEFAULT_BENEFICIO),
                "cofins": deepcopy(_DEFAULT_BENEFICIO),
            },
            "afrmm": deepcopy(_DEFAULT_AFRMM),
            "icms": deepcopy(_DEFAULT_ICMS),
            "destinacao": "REVENDA",
            "subtipoConsumo": None,
        },
        "exportacao": {
            "analistaDA": "",
            "produtosExportados": "",
            "ncms": [],
            "portosFronteiras": [],
            "outroPorto": None,
            "outraFronteira": None,
            "destinacao": "REVENDA",
            "subtipoConsumo": None,
        },
    },
    "servicos": {
        "importacao": {
            "despachoAduaneiroImportacao": deepcopy(_DEFAULT_SERVICO_VALOR_OU_SALARIO),
            "preposto": deepcopy(_DEFAULT_SERVICO_PREPOSTO),
            "emissaoLiLpco": deepcopy(_DEFAULT_SERVICO_VALOR_SIMPLES),
            "cadastroCatalogoProdutos": deepcopy(_DEFAULT_SERVICO_VALOR_SIMPLES),
            "assessoria": deepcopy(_DEFAULT_SERVICO_VALOR_OU_SALARIO),
            "freteInternacional": deepcopy(_DEFAULT_SERVICO_FRETE_INTERNACIONAL),
            "seguroInternacional": deepcopy(_DEFAULT_SERVICO_SEGURO),
            "freteRodoviario": deepcopy(_DEFAULT_SERVICO_FRETE_RODOVIARIO),
            "regimeEspecial": [],
            "emissaoNfe": deepcopy(_DEFAULT_SERVICO_VALOR_SIMPLES),
        },
        "exportacao": {
            "despachoAduaneiroExportacao": deepcopy(_DEFAULT_SERVICO_VALOR_OU_SALARIO),
            "preposto": deepcopy(_DEFAULT_SERVICO_PREPOSTO),
            "certificadoOrigem": deepcopy(_DEFAULT_SERVICO_VALOR_SIMPLES),
            "certificadoFitossanitario": deepcopy(_DEFAULT_SERVICO_VALOR_SIMPLES),
            "outrosCertificados": {"habilitado": False, "itens": []},
            "assessoria": deepcopy(_DEFAULT_SERVICO_VALOR_OU_SALARIO),
            "freteInternacional": deepcopy(_DEFAULT_SERVICO_FRETE_INTERNACIONAL),
            "seguroInternacional": deepcopy(_DEFAULT_SERVICO_SEGURO),
            "freteRodoviario": deepcopy(_DEFAULT_SERVICO_FRETE_RODOVIARIO),
            "regimeEspecial": [],
        },
    },
    "financeiro": {
        "dadosBancariosClienteDevolucaoSaldo": deepcopy(_DEFAULT_BANK_ACCOUNT),
        "observacoesFinanceiro": "",
    },
}

def build_default_scope_draft() -> dict:
    return deepcopy(DEFAULT_SCOPE_DRAFT)


def merge_scope_draft(base: dict, patch: dict) -> dict:
    if not isinstance(base, dict):
        return deepcopy(patch)

    result = deepcopy(base)
    if not isinstance(patch, dict):
        return result

    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_scope_draft(result[key], value)
        else:
            result[key] = value
    return result


def apply_admin_defaults(draft: dict, admin_settings: dict | None) -> dict:
    normalized = merge_scope_draft(build_default_scope_draft(), draft)
    if not admin_settings:
        return normalized

    normalized["informacoesFixas"] = {
        "salarioMinimoVigente": admin_settings.get("salarioMinimoVigente", 0),
        "dadosBancariosCasco": merge_scope_draft(
            deepcopy(_DEFAULT_BANK_ACCOUNT),
            admin_settings.get("dadosBancariosCasco", {}),
        ),
    }
    return normalized