# Alteração em massa de escopos

O fluxo de alteração em massa está disponível para usuários autenticados e possui quatro etapas:

1. pesquisar, filtrar e selecionar os escopos;
2. escolher um campo e um usuário de destino;
3. revisar a prévia e os registros ignorados;
4. aplicar as mudanças em lotes de até 50 escopos pelo cliente.

## Pesquisa e filtros

`GET /scopes/bulk/candidates` aceita:

- `q`: palavras pesquisadas, em conjunto, na razão social, nome resumido, CNPJ,
  status e conteúdo JSON do escopo;
- `status`: `draft`, `published` ou `archived`;
- `operation`: `IMPORTACAO` ou `EXPORTACAO`;
- `tagId`: retorna escopos vinculados a usuários com a tag informada;
- `limit` e `offset`: paginação, limitada a 200 registros por página.

As consultas e atualizações são sempre limitadas à organização do usuário. Usuários
não administradores podem trabalhar com escopos publicados e com os próprios
rascunhos; rascunhos de outros autores não são listados nem alterados. Administradores
mantêm acesso a todos os escopos da organização.

## Campos alteráveis

- `responsavel_comercial`;
- `analista_da_importacao`;
- `analista_ae_importacao`;
- `analista_da_exportacao`;
- `analista_ae_exportacao`.

O usuário de destino deve estar ativo e possuir a tag correspondente ao campo.
Campos de importação ou exportação só são aplicados quando aquela operação existe
no schema do escopo.

## Prévia e execução

`POST /scopes/bulk/preview` não modifica dados. Ele separa os escopos entre:

- elegíveis;
- operação incompatível;
- valor já aplicado;
- inexistente, fora da organização ou sem permissão.

`POST /scopes/bulk/apply` aceita o mesmo corpo e é idempotente:

```json
{
  "field": "analista_da_importacao",
  "targetUserId": "uuid",
  "scopeIds": ["uuid"]
}
```

Para escopos publicados, a operação atualiza `draft`, `published_snapshot`,
atribuições relacionais e cria uma nova `ScopeVersion`. Rascunhos permanecem
restritos ao autor e aos administradores nas demais consultas da plataforma.

A interface exige uma confirmação explícita, com o resumo do campo, usuário de
destino e quantidade de escopos, antes de chamar o endpoint de aplicação.

Não há nova migration neste checkpoint.
