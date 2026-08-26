# Cadastro de transportadoras da NF-e

O Checkpoint 4D adiciona o catálogo organizacional `nfe_carriers`. O cadastro é
isolado por `organization_id`; usuários autenticados podem consultar e apenas
administradores podem criar, editar, desativar ou reativar registros.

## Endpoints

```http
GET    /nfe-carriers?q=transportadora&active=true&limit=25&offset=0
POST   /nfe-carriers
GET    /nfe-carriers/{carrier_id}
PATCH  /nfe-carriers/{carrier_id}
DELETE /nfe-carriers/{carrier_id}
```

`DELETE` realiza desativação lógica (`active=false`). Um CPF/CNPJ pode aparecer
uma única vez dentro da mesma organização.

O município é recebido pelo código IBGE. A API consulta
`fiscal_municipalities` e grava `municipality_name` e `state` a partir da
referência fiscal ativa, sem confiar em texto livre enviado pelo frontend.

## Cópia para o rascunho

Na revisão, uma transportadora cadastrada pode ser selecionada com:

```json
{
  "transport": {
    "freight_mode": "0",
    "carrier_id": "UUID_DA_TRANSPORTADORA"
  }
}
```

A API resolve o registro dentro da organização e copia todos os dados para
`nfe_drafts.fiscal_payload.transport.carrier`. Alterações posteriores no
cadastro não modificam rascunhos ou XMLs anteriores.

O preenchimento manual continua disponível pelo objeto `transport.carrier`.
`carrier_id` e `carrier` não podem ser enviados juntos.

## Banco de dados

A model foi adicionada ao metadata do SQLAlchemy. Este checkpoint não cria nem
executa migration; a alteração física da tabela deve ser gerada e aplicada pelo
responsável no ambiente autorizado.
