from app.services.duimp_normalizer import DuimpNormalizer


def test_builds_nfe_product_description_at_word_boundary():
    result = DuimpNormalizer._nfe_product_description(
        "PRODUTO SINTETICO COM DENOMINACAO COMPLETA",
        (
            "DETALHAMENTO SINTETICO COM CARACTERISTICAS ADICIONAIS PARA "
            "VALIDAR O LIMITE DO CAMPO SEM DADOS OPERACIONAIS"
        ),
    )

    assert len(result) <= 120
    assert result == (
        "PRODUTO SINTETICO COM DENOMINACAO COMPLETA DETALHAMENTO SINTETICO "
        "COM CARACTERISTICAS ADICIONAIS PARA VALIDAR O LIMITE"
    )
