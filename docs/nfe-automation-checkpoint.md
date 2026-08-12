# Checkpoint: contexto automatizado e regras fiscais da NF-e de importação

Este checkpoint reduz o payload digitado a cada processo sem transformar
inferências em fatos fiscais. As integrações CCT, PCCE e TABX executam apenas
consultas `GET`. Campos que não possam ser confirmados permanecem em
`missing_fields` e devem ser informados explicitamente antes do rascunho.

## 1. Migração

O model `ClientImportTaxRule` cria a tabela `client_import_tax_rules`. Conforme
o fluxo de migrações do projeto, gere e revise a migration no ambiente local:

```bash
alembic revision --autogenerate -m "add client import tax rules"
alembic upgrade head
```

Nenhuma migration Alembic foi incluída neste checkpoint.

## 2. Configuração opcional da conexão Portal Único

O `config_json` da conexão aceita estas chaves para enriquecimento TABX:

```json
{
  "role_type": "IMPEXP",
  "tabx_customs_unit_table": "NOME_CONFIRMADO_NA_TABX",
  "tabx_customs_unit_code_field": "CODIGO",
  "tabx_customs_unit_description_field": "NOME",
  "tabx_customs_unit_state_field": "UF",
  "tabx_country_table": "NOME_CONFIRMADO_NA_TABX",
  "tabx_country_iso_field": "SIGLA_ISO2",
  "tabx_country_code_field": "CODIGO",
  "tabx_country_name_field": "NOME",
  "country_code_map": {
    "US": "2496"
  }
}
```

Os nomes de tabela/campo devem ser confirmados nos metadados TABX disponíveis
para a credencial. Se não estiverem configurados, a API usa somente referências
oficiais incorporadas e identificadas como `builtin_official_reference`. Neste
checkpoint estão cadastrados `0927800 -> ALF/PORTO DE ITAJAI, SC` e
`US -> 2496, ESTADOS UNIDOS`. Outros códigos continuam pendentes até serem
resolvidos pelo TABX, pela configuração da conexão ou pelo operador.

## 3. Cadastro único de regra fiscal por cliente

Exemplo para uma operação de revenda, importação direta, emitente do Paraná:

```http
POST /clients/{client_id}/import-tax-rules
Content-Type: application/json
```

```json
{
  "name": "PR - revenda - direta - padrão",
  "issuer_state": "PR",
  "import_purpose": "resale",
  "import_modality": "direct",
  "tax_regime": "3",
  "priority": 100,
  "configuration_json": {
    "icms_rate": "12",
    "icms_origin": "1",
    "icms_cst": "90",
    "ipi_cst": "49",
    "pis_cst": "98",
    "cofins_cst": "98"
  },
  "transport_defaults": {
    "freight_mode": "9"
  },
  "payment_defaults": {
    "method": "90",
    "value": "0.00"
  },
  "active": true
}
```

Use `ncm_pattern` quando uma regra for válida somente para um NCM ou prefixo.
A regra mais específica é selecionada por prioridade, tamanho do padrão NCM,
modalidade e regime tributário. As alíquotas e CSTs precisam ser validados pelo
responsável fiscal antes de habilitar a regra.

Endpoints de manutenção:

- `GET /clients/{client_id}/import-tax-rules`
- `PUT /clients/{client_id}/import-tax-rules/{rule_id}`
- `DELETE /clients/{client_id}/import-tax-rules/{rule_id}` (inativa; não apaga)

## 4. Fluxo de uma nova NF-e

Crie o processo e capture a DUIMP como já feito hoje. Uma DUIMP real normalmente
é consultada em `production`, mesmo quando a NF-e será gerada em homologação:

```http
POST /import-processes/{process_id}/duimp/fetch
```

```json
{
  "provider_environment": "production",
  "enrich_catalog": true
}
```

Em seguida resolva e persista o contexto:

```http
POST /import-processes/{process_id}/nfe-context/resolve
```

```json
{
  "duimp_snapshot_id": "UUID_DO_SNAPSHOT",
  "import_purpose": "resale",
  "provider_environment": "production",
  "refresh_external": true,
  "overrides": {}
}
```

A resposta apresenta cada campo com `value`, `source` e `status`, além de
`missing_fields`, `tax_rule`, referências fiscais do PCCE e sugestões. Falhas
isoladas nas fontes externas aparecem em `external.errors`.

Se ainda houver pendências, envie somente os dados confirmados pelo operador:

```json
{
  "duimp_snapshot_id": "UUID_DO_SNAPSHOT",
  "import_purpose": "resale",
  "refresh_external": false,
  "overrides": {
    "clearance_location": "PORTO DE PARANAGUA",
    "clearance_state": "PR",
    "clearance_date": "2026-07-15",
    "transport_mode_code": "1",
    "foreign_supplier": {
      "country_code": "1600",
      "country_name": "CHINA"
    }
  }
}
```

Para consultar o diagnóstico sem persistir alterações:

```http
GET /import-processes/{process_id}/nfe-context?import_purpose=resale&duimp_snapshot_id={snapshot_id}
```

Quando `ready_for_draft=true`, o rascunho pode ser criado com payload mínimo:

```http
POST /import-processes/{process_id}/nfe-draft/from-duimp
```

```json
{
  "environment": "homologation",
  "series": "1",
  "import_purpose": "resale",
  "duimp_snapshot_id": "UUID_DO_SNAPSHOT"
}
```

`tax_configuration` continua aceito como override explícito para exceções. Sem
ele, a API exige uma regra fiscal aplicável. O draft registra
`source.tax_configuration_source` e `source.tax_rule_id` para auditoria.

Depois, prossiga com os endpoints já existentes:

1. `POST /nfe-drafts/{draft_id}/generate-access-key`
2. `POST /nfe-drafts/{draft_id}/generate-xml`
3. `POST /nfe-drafts/{draft_id}/xml-versions/{xml_version_id}/validate-xsd`
4. conferir reconciliação, totais e referências do processo;
5. somente depois assinar e transmitir em homologação.

## 5. XML diagnóstico com ICMS CST 51

Quando o Portal/PCCE e a documentação fiscal comprovarem diferimento integral,
mas a alíquota nominal e o enquadramento do TTD ainda não estiverem confirmados,
é possível cadastrar uma regra exclusiva de diagnóstico:

```http
POST /clients/daba0bf1-43b4-42be-a8a5-b4326307366e/import-tax-rules
Content-Type: application/json
```

```json
{
  "name": "SC - industrialização direta - diferimento integral diagnóstico",
  "issuer_state": "SC",
  "import_purpose": "industrialization",
  "import_modality": "direct",
  "tax_regime": "3",
  "ncm_pattern": "84",
  "priority": 100,
  "configuration_json": {
    "icms_origin": "1",
    "icms_cst": "51",
    "icms_base_method": "3",
    "icms_deferment_rate": "100",
    "icms_base_allocation": "proportional_customs_value",
    "ipi_cst": "49",
    "ipi_enquiry_code": "999",
    "pis_cst": "98",
    "cofins_cst": "98"
  },
  "additional_cost_defaults": {
    "afrmm": "0",
    "thc": "0",
    "other": "0"
  },
  "transport_defaults": {
    "freight_mode": "9"
  },
  "payment_defaults": {
    "method": "90",
    "value": "0.00"
  },
  "active": true,
  "effective_from": "2026-01-01"
}
```

Sem `icms_rate`, o XML contém `ICMS51`, `vBC`, `pDif=100` e `vICMS=0`,
omitindo `pICMS`, `vICMSOp` e `vICMSDif`. O draft recebe:

```json
{
  "authorization": {
    "ready": false,
    "mode": "diagnostic",
    "blockers": [
      {
        "code": "missing_nominal_icms_rate"
      }
    ]
  }
}
```

Esse bloqueio deve ser obrigatoriamente verificado pelo futuro endpoint de
transmissão. A geração, o download e a validação XSD do XML diagnóstico
continuam disponíveis para conferência. A assinatura não remove o bloqueio.

Para a DUIMP `26BR0000684087-7`, persista a data confirmada no histórico:

```json
{
  "duimp_snapshot_id": "d4a60485-8309-47d7-b535-7bb3fe2136cc",
  "import_purpose": "industrialization",
  "refresh_external": false,
  "overrides": {
    "clearance_date": "2026-05-27"
  }
}
```

Após o novo `duimp/fetch`, a normalização também:

- consulta o CCT pelo AWB do documento de instrução tipo `30`, antes da RUC;
- deriva adição e sequência a partir de `dadosGerais.adicoes`;
- normaliza `UNIDADE` para `UN`;
- conserva a descrição CATP completa em `infAdProd` quando `xProd` ultrapassa
  120 caracteres;
- aplica `cFabricante=0000` apenas quando o Portal retornou explicitamente o
  fabricante sem código, registrando a origem do fallback e um aviso.

## Referências oficiais

- [CCT Importação — consultas e operações](https://docs.portalunico.siscomex.gov.br/api/ccta/consultas/)
- [Pagamento Centralizado do Comércio Exterior (PCCE)](https://docs.portalunico.siscomex.gov.br/api/pcce/)
- [Tabelas Comex (TABX)](https://docs.portalunico.siscomex.gov.br/api/tabx/)
