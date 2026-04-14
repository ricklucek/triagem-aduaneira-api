# Endpoints da API — Triagem Aduaneira

## Convenções
- **Auth:** JWT Bearer no header `Authorization: Bearer <token>`.
- **Tenant:** consultas de escopo/usuários são filtradas por `organization_id` do usuário autenticado.
- **Formato de erro padrão:** `{"error": "mensagem"}` ou `{"message": "mensagem", "errors": {...}}`.

---

## Auth

### `POST /auth/register`
Cria usuário e vincula a uma organização existente (`organization_id`) ou cria uma nova organização.

**Body**
```json
{
  "nome": "Nome",
  "email": "user@dominio.com",
  "password": "senha-com-8-ou-mais",
  "role": "admin",
  "setor": "comercial",
  "organization_id": "uuid-opcional",
  "organization_nome": "Empresa XYZ",
  "organization_slug": "empresa-xyz",
  "organization_cnpj": "12345678000199"
}
```

**Regras**
- `organization_id` **ou** `organization_nome` é obrigatório.
- Email deve ser único.

**Resposta 201**
```json
{
  "user": {"id": "...", "nome": "...", "email": "...", "role": "...", "organizationId": "..."},
  "tokens": {"accessToken": "...", "refreshToken": "...", "expiresIn": 3600}
}
```

### `POST /auth/login`
Autentica usuário ativo.

### `POST /auth/refresh`
Invalida o refresh token atual e emite novo par de tokens.

### `POST /auth/logout`
Revoga todos os refresh tokens ativos do usuário logado.

### `GET /auth/me`
Retorna identidade do usuário autenticado.

---

## Admin

### `GET /admin/settings`
Retorna configurações fixas da organização (`scope_fixed_info`).

### `PUT /admin/settings`
Atualiza configurações fixas por organização.

**Body**
```json
{
  "salarioMinimoVigente": 1621.0,
  "dadosBancariosCasco": {"banco": "001", "agencia": "4500", "conta": "24438-4"}
}
```

---

## Usuários

### `GET /users`
Lista usuários ativos da organização (somente admin).

### `GET /users/responsibles`
Lista possíveis responsáveis ativos da organização.

### `POST /users`
Cria usuário na organização do admin logado.

### `PUT /users/user/<user_id>`
Atualiza usuário.

### `DELETE /users/user/<user_id>`
Desativa usuário (`ativo=false`).

---

## Escopos

### `GET /scopes/metadata`
Retorna:
- `informacoesFixas` (configuração da organização)
- `responsaveis` (usuários ativos)

### `POST /scopes`
Cria escopo com draft normalizado e score de completude.

### `GET /scopes`
Lista escopos com paginação e filtros.

**Query params**
- `status`
- `q` (busca textual em razão social/cnpj/status)
- `cnpj`
- `client_id`
- `responsible_user_id`
- `created_by_id`
- `limit` (1..200)
- `offset` (>=0)

### `GET /scopes/<scope_id>`
Retorna escopo completo com relacionamentos serializados por `SQLAlchemyAutoSchema`.

### `PUT /scopes/<scope_id>`
Atualiza draft completo do escopo.

### `POST /scopes/<scope_id>/publish`
Publica escopo:
1. normaliza draft,
2. cria/atualiza `Client` a partir de `sobreEmpresa`,
3. salva snapshot publicado,
4. incrementa versão,
5. cria registro em `scope_versions`.

### `GET /scopes/<scope_id>/versions`
Lista histórico de versões do escopo.

### `POST /scopes/bulk/reassign-responsible`
Edição em massa para troca de responsável comercial.

**Body**
```json
{
  "old_user_id": "uuid-antigo",
  "new_user_id": "uuid-novo",
  "apply_status": ["draft", "published"],
  "only_active_assignments": true,
  "dry_run": true
}
```

**Regras**
- Sempre filtra no tenant da organização do usuário.
- `dry_run=true`: retorna somente impacto (`count` + `impactedScopes`).
- `dry_run=false`: atualiza `scope.responsible_user_id`, encerra assignment ativo anterior e cria novo `ScopeAssignment` com role `RESPONSAVEL_COMERCIAL`.

### `DELETE /scopes/<scope_id>`
Exclui escopo.

---

## Prepostos

Mantidos os endpoints existentes de CRUD de prepostos, contatos e localidades:
- `POST /prepostos`
- `GET /prepostos`
- `GET /prepostos/<id>`
- `PATCH /prepostos/<id>`
- `DELETE /prepostos/<id>`
- `POST /prepostos/<id>/contatos`
- `PATCH /prepostos/<id>/contatos/<contato_id>`
- `DELETE /prepostos/<id>/contatos/<contato_id>`
- `POST /prepostos/<id>/localidades`
- `PATCH /prepostos/<id>/localidades/<localidade_id>`
- `DELETE /prepostos/<id>/localidades/<localidade_id>`
- `GET /prepostos/lookup`
