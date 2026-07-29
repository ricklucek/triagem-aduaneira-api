# Teste da NF-e de importação até o XML não assinado

Este fluxo cobre a consulta da DUIMP, criação do rascunho fiscal, cálculo dos
tributos, geração da chave e geração da NF-e 4.00. Assinatura com certificado,
validação XSD oficial e transmissão à SEFAZ ficam propositalmente fora desta
etapa.

Todos os endpoints exigem `Authorization: Bearer <accessToken>`.

## 1. Preparar o ambiente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

O teste de integração `tests/integration/test_import_nfe_api_flow.py` executa o
fluxo completo em SQLite, com dados sanitizados, e confirma que o XML não tem
uma assinatura digital.

## 2. Configurar o perfil fiscal do emitente

Use `PUT /clients/{client_id}/fiscal-profile`. A UF informada aqui define o
`cUF`, o endereço do emitente e a chave de acesso da NF-e; ela não é fixa no
sistema.

Campos essenciais: CNPJ, IE, CRT, logradouro, município/IBGE, UF e CEP.

Se o número da NF-e não for enviado ao criar o rascunho, configure também a
sequência com `PUT /clients/{client_id}/nfe-number-sequences`.

## 3. Configurar o Portal Único

Cadastre uma conexão em `POST /external-provider-connections`:

```json
{
  "importer_id": "UUID_DO_CLIENTE",
  "provider": "portal_unico",
  "environment": "production",
  "auth_type": "api_key",
  "status": "active",
  "credentials_ref": "env:CLIENTE_ACME_PORTAL",
  "config_json": {"role_type": "IMPEXP", "timeout_seconds": 30}
}
```

As chaves não são gravadas no banco. Configure-as no processo da aplicação:

```bash
export CLIENTE_ACME_PORTAL_CLIENT_ID='...'
export CLIENTE_ACME_PORTAL_CLIENT_SECRET='...'
```

O backend autentica em `/portal/api/autenticar/chave-acesso`, conserva os
headers de token/CSRF e consulta versão, dados gerais e todas as páginas de
itens (até 100 itens por página).

## 4. Criar o processo e capturar a DUIMP

Crie o processo:

```http
POST /import-processes
```

```json
{
  "importer_id": "UUID_DO_CLIENTE",
  "reference_code": "PROCESSO-INTERNO-001",
  "duimp_number": "26BR0000000000-1",
  "source": "portal_unico"
}
```

Capture e persista o snapshot:

```http
POST /import-processes/{process_id}/duimp/fetch
```

```json
{
  "provider_environment": "production",
  "source_provider": "portal_unico",
  "enrich_catalog": true
}
```

O backend aceita a forma digitada (`26BR0000000000-1`) e envia à API a forma
compacta (`26BR00000000001`). A resposta guarda tanto o JSON bruto quanto o
contrato normalizado e seu checksum. Com `enrich_catalog=true`, cada produto e
operador estrangeiro referenciado nos itens também é consultado no Catálogo de
Produtos do Portal Único. Consultas repetidas são reaproveitadas durante a
mesma captura.

Confira `normalized_payload.catalog_enrichment` antes de criar o rascunho:

```json
{
  "products_requested": 72,
  "products_enriched": 72,
  "operators_requested": 1,
  "operators_enriched": 1,
  "failures": []
}
```

Os totais `*_enriched` devem coincidir com `*_requested` e `failures` deve
estar vazio. O rascunho fiscal rejeita a descrição genérica
`Mercadoria importada`, evitando gerar chave ou XML com um item ainda não
enriquecido.

## 5. Criar o rascunho fiscal

```http
POST /import-processes/{process_id}/nfe-draft/from-duimp
```

Exemplo mínimo para importação própria:

```json
{
  "environment": "homologation",
  "provider_environment": "production",
  "series": "1",
  "number": 123,
  "import_purpose": "resale",
  "source_provider": "portal_unico",
  "duimp_snapshot_id": "UUID_RETORNADO_NA_CAPTURA",
  "tax_configuration": {
    "icms_rate": "12",
    "icms_origin": "1",
    "icms_cst": "90",
    "ipi_cst": "49",
    "pis_cst": "98",
    "cofins_cst": "98",
    "tax_classification_code": "000001",
    "ibs_cbs_cst": "000",
    "ibs_uf_rate": "0.1",
    "ibs_mun_rate": "0",
    "cbs_rate": "0.9"
  },
  "additional_costs": {
    "siscomex_fee": "0.00",
    "thc": "0.00",
    "afrmm": "0.00",
    "other": "0.00"
  },
  "foreign_supplier": {
    "name": "FOREIGN SUPPLIER LTD",
    "foreign_id": "",
    "country_code": "1600",
    "country_name": "CHINA",
    "address": {
      "street": "EXTERIOR",
      "number": "0",
      "district": "EXTERIOR",
      "city_name": "EXTERIOR"
    }
  }
}
```

`foreign_supplier` continua disponível como sobrescrita quando o cadastro do
operador estrangeiro não tiver código BACEN ou endereço suficientes para a
NF-e. Nome e endereço são preenchidos automaticamente pelo Catálogo quando
estiverem disponíveis.

O valor do produto na NF-e é o valor aduaneiro da DUIMP, que já contém frete e
seguro. Por isso, `vFrete` e `vSeg` não são somados novamente. Siscomex, THC e
outras despesas são rateadas proporcionalmente ao valor aduaneiro; o AFRMM é
rateado pelo peso líquido. Quando houver AFRMM e mais de um item, todos os itens
precisam ter peso líquido positivo.

Os rateios fecham exatamente no total informado usando distribuição do resíduo
pelas maiores frações de centavo. O ICMS é calculado "por dentro". Os valores
de II, IPI, PIS e COFINS dos itens vêm da DUIMP e não são recalculados.

O payload fiscal inclui `reconciliation`. O status `balanced` confirma que os
totais oficiais disponíveis na DUIMP e todos os custos informados fecharam; o
status `requires_review` bloqueia a geração da chave e do XML até a divergência
ser corrigida.

## 6. Gerar chave e XML

```http
POST /nfe-drafts/{draft_id}/generate-access-key
Content-Type: application/json

{}
```

```http
POST /nfe-drafts/{draft_id}/generate-xml
Content-Type: application/json

{}
```

O segundo endpoint persiste uma versão `unsigned`. Verifique no XML:

- `infNFe/@Id` com a chave de 44 dígitos;
- `tpNF=0` e `idDest=3`;
- emitente brasileiro e destinatário estrangeiro (`UF=EX`);
- um grupo `DI` em cada item;
- totais de ICMS, II, IPI, PIS, COFINS e, quando configurado, IBS/CBS;
- ausência do grupo XMLDSig `Signature`.

## Modalidades

O normalizador reconhece `direct`, `on_behalf` e `by_order`. Para conta e ordem
ou encomenda, informe também em `duimp_overrides`:

```json
{
  "intermediation_type": "2",
  "third_party_tax_id": "CNPJ_OU_CPF",
  "third_party_state": "SP"
}
```

Use `intermediation_type=2` para conta e ordem e `3` para encomenda. Esta etapa
gera a NF-e de entrada vinculada à DUIMP. Eventuais notas subsequentes entre a
importadora e adquirente/encomendante devem ser tratadas como outro documento
fiscal, com regras próprias.

## Limites desta etapa

- Ainda não há assinatura A1/A3, transmissão, recibo, protocolo ou eventos.
- A validação estrutural está coberta por testes, mas `xsd_valid` permanece
  indefinido até a inclusão do pacote oficial de schemas vigente.
- O cálculo usa parâmetros explícitos porque ICMS e benefícios dependem da UF,
  NCM, finalidade, regime e enquadramento do cliente.
- Antes de produção, compare uma amostra representativa com o cálculo do
  despachante/ERP e execute a autorização no ambiente de homologação da SEFAZ.
