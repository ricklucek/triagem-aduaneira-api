# Endpoints da API — Triagem Aduaneira

## Convenções
- **Auth:** JWT Bearer no header `Authorization: Bearer <token>`.
- **Tenant:** consultas de escopo/usuários/clientes são filtradas por `organization_id` do usuário autenticado.
- **Formato de erro padrão:** `{"error": "mensagem"}` ou `{"message": "mensagem", "errors": {...}}`.

---

## Auth
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`

---

## Organizações (novo grupo principal)

### `GET /organizations/me`
Retorna metadados da organização atual e `fixedInfo` usada nos escopos.

### `GET /organizations/me/settings`
Retorna informações fixas da organização (`scope_fixed_info`):
```json
{
  "salarioMinimoVigente": 1621.0,
  "dadosBancariosCasco": {"banco": "001", "agencia": "4500", "conta": "24438-4"}
}
```

### `PUT /organizations/me/settings` (admin)
Atualiza informações fixas da organização.

> **Observação:** `GET/PUT /admin/settings` estão **deprecated** e retornam `410` com instrução de migração.

---

## Clientes

### `GET /clients`
Lista clientes da organização com filtros:
- `q` (nome resumido/razão social/cnpj)
- `cnpj`
- `ativo`
- `limit`
- `offset`

### `GET /clients/<client_id>`
Detalha um cliente.

### `PATCH /clients/<client_id>`
Atualiza dados cadastrais de cliente.

### `GET /clients/<client_id>/scopes`
Lista escopos associados ao cliente.

Filtros:
- `status`
- `limit`
- `offset`

---

## Usuários
- `GET /users` (admin)
- `GET /users/responsibles`
- `POST /users` (admin)
- `PUT /users/user/<user_id>` (admin)
- `DELETE /users/user/<user_id>` (admin)

---

## Escopos

### `GET /scopes/metadata`
Retorna:
- `informacoesFixas` (settings da organização)
- `responsaveis` (usuários ativos)

### `POST /scopes`
Cria escopo com `draft` completo e aninhado (JSON livre), com normalização e score de completude.

### `GET /scopes`
Lista escopos com filtros:
- `status`, `q`, `cnpj`, `client_id`, `responsible_user_id`, `created_by_id`, `limit`, `offset`

### `GET /scopes/<scope_id>`
Retorna escopo completo com relacionamentos via `SQLAlchemyAutoSchema`.

### `PUT /scopes/<scope_id>`
Atualiza `draft` completo (aceita objeto JSON aninhado).

### `POST /scopes/<scope_id>/publish`
Publica escopo, faz upsert do cliente e cria versão (`scope_versions`).

### `GET /scopes/<scope_id>/versions`
Lista histórico de versões do escopo.

### `POST /scopes/bulk/reassign-responsible`
Edição em massa para troca de responsável comercial.

### `DELETE /scopes/<scope_id>`
Exclui escopo.

---

## Prepostos
Mantidos endpoints de CRUD e lookup já existentes.
