# Alteração em massa de escopos

O fluxo de alteração em massa está disponível para usuários autenticados e possui quatro etapas:

1. pesquisar, filtrar e selecionar os escopos;
2. escolher um campo e um usuário de destino;
3. revisar a prévia e os registros ignorados;
4. aplicar as mudanças em lotes de até 50 escopos pelo cliente.

## Pesquisa e filtros

`GET /scopes/bulk/candidates` lista exclusivamente escopos publicados e aceita:

- `q`: palavras pesquisadas, em conjunto, na razão social, nome resumido, CNPJ,
  e conteúdo JSON do escopo;
- `commercialUserIds`: responsáveis comerciais, separados por vírgula;
- `analystDaUserIds`: analistas DA, separados por vírgula;
- `analystAeUserIds`: analistas AE, separados por vírgula;
- `limit` e `offset`: paginação, limitada a 200 registros por página.

Dentro do mesmo grupo de pessoas, o filtro usa lógica OU. Entre grupos, utiliza
lógica E. Importação e exportação permanecem juntas na listagem e não possuem filtro
de operação. Na interface, as pessoas são agrupadas por função e cada seleção aparece
como uma tag removível.

As consultas e atualizações são sempre limitadas à organização do usuário e a escopos
publicados. Rascunhos e escopos arquivados não são listados, aceitos na prévia ou
alterados, inclusive para administradores.

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

A operação atualiza `draft`, `published_snapshot`, atribuições relacionais e cria
uma nova `ScopeVersion`.

A interface exige uma confirmação explícita, com o resumo do campo, usuário de
destino e quantidade de escopos, antes de chamar o endpoint de aplicação.

Não há nova migration neste checkpoint.
