# Endpoints de Scope (contratos de request)

## POST `/scopes`
Cria um escopo e já materializa dados no modelo relacional.

### Body esperado
Payload no formato legado de preenchimento (usado para sincronizar relacional):
- `sobreEmpresa` (objeto)
  - `cnpj` (string)
  - `razaoSocial` (string)
  - `nomeResumido` (string, opcional)
  - `inscricaoEstadual` (string, opcional)
  - `inscricaoMunicipal` (string, opcional)
  - `enderecoCompletoEscritorio` (string, opcional)
  - `enderecoCompletoArmazem` (string, opcional)
  - `cnaePrincipal` (string, opcional)
  - `cnaeSecundario` (string, opcional)
  - `regimeTributacao` (string, opcional)
  - `responsavelComercial`/`responsavelComercialId` (uuid, opcional)
- `operacao` (objeto com `importacao` e/ou `exportacao`)
  - `analistaDA` (array de uuid)
  - `analistaAE` (array de uuid)
- `servicos` (objeto por operação e serviço)

## PUT `/scopes/<scope_id>`
Atualiza dados de escopo e ressincroniza tabelas relacionais com base no payload enviado.

### Body esperado
Mesmo formato do `POST /scopes`.

## PUT `/scopes/<scope_id>/draft`
Salva somente rascunho incompleto do usuário na coluna legada (`draft`), sem sincronizar dados relacionais.

### Body esperado
Qualquer JSON parcial de preenchimento de formulário de escopo.

## POST `/scopes/<scope_id>/publish`
Publica o escopo usando o estado já materializado no relacional e salva snapshot publicado.

### Body esperado
Mesmo formato do `POST /scopes` (estado final a publicar).

## GET `/scopes`
Lista escopos.

### Query params
- `status`
- `client_id`
- `responsible_user_id`
- `created_by_id`
- `assigned_user_id`
- `cnpj`
- `q`
- `limit`
- `offset`

## GET `/scopes/<scope_id>`
Retorna escopo estruturado para consumo de front-end.

## GET `/scopes/<scope_id>/versions`
Lista versões publicadas.

## DELETE `/scopes/<scope_id>`
Remove escopo.
