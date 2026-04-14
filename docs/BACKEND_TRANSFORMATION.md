# Transformação do Backend e Impactos no Front-end

## 1) Contexto da migração
Antes, a maior parte dos dados do formulário ficava concentrada no `Scope.draft` e quase toda consulta/listagem dependia de leitura desse JSON bruto.

Agora, o backend foi evoluído para um modelo **híbrido**:
- mantém o `draft` para compatibilidade e evolução incremental do front;
- normaliza entidades críticas em tabelas relacionais (`Organization`, `Client`, `ScopeAssignment`, `ScopeVersion`, etc.) para busca, filtros e operações em massa.

## 2) O que mudou estruturalmente

### 2.1 Multi-tenant por organização
Todos os recursos principais (escopos, clientes, usuários) são filtrados por `organization_id` do usuário autenticado.

### 2.2 Informações fixas movidas para organização
As informações fixas usadas no escopo (`salarioMinimoVigente`, `dadosBancariosCasco`) saíram do domínio de admin legado e passam a viver em:
- `OrganizationSetting` (key: `scope_fixed_info`)
- endpoints `/organizations/me/settings`

### 2.3 Publicação passa a consolidar dados relacionais
No `publish` do escopo:
1. draft é normalizado;
2. cliente é criado/atualizado via `sobreEmpresa` (`cnpj`, `razaoSocial`, etc.);
3. snapshot publicado é salvo;
4. versão do escopo é incrementada;
5. histórico em `scope_versions` é criado.

### 2.4 Edição em massa de responsável
Novo endpoint de bulk edit permite trocar `responsavelComercial` em múltiplos escopos com:
- `dry_run` para prever impacto;
- filtros por status;
- manutenção de trilha em `ScopeAssignment`.

## 3) Garantia de compatibilidade com JSON aninhado
`POST /scopes` e `PUT /scopes/<id>` aceitam objeto JSON aninhado completo (como o payload extenso que vocês já enviam). O backend aplica normalização sem quebrar subestruturas (`operacao`, `servicos`, `financeiro`, etc.) desde que o payload seja um objeto JSON válido.

## 4) Novos endpoints para o front

## Organização
- `GET /organizations/me`
- `GET /organizations/me/settings`
- `PUT /organizations/me/settings` (admin)

## Clientes
- `GET /clients`
- `GET /clients/<client_id>`
- `PATCH /clients/<client_id>`
- `GET /clients/<client_id>/scopes`

## Escopos (já evoluídos)
- `GET /scopes` com filtros escaláveis
- `POST /scopes/bulk/reassign-responsible`
- `POST /scopes/<id>/publish` com upsert de cliente + versionamento

## 5) Mudanças que o front deve aplicar
1. **Configurações fixas:** migrar consumo de `/admin/settings` para `/organizations/me/settings`.
2. **Clientes:** usar `/clients` para listagens e edição cadastral, evitando depender apenas de `draft` para telas de consulta.
3. **Escopos por cliente:** usar `/clients/<id>/scopes` quando a UI estiver no contexto de cliente.
4. **Troca de responsável em massa:** usar `dry_run=true` antes da execução final.
5. **Draft completo:** continuar enviando o objeto aninhado completo no save do escopo.

## 6) Endpoints legados/deprecated
- `GET /admin/settings` e `PUT /admin/settings`: retornam `410` e instruem uso de `/organizations/me/settings`.

## 7) Recomendações de rollout
- Fase 1: front troca `/admin/settings` por `/organizations/me/settings`.
- Fase 2: telas de cliente passam a consumir `/clients` e `/clients/<id>/scopes`.
- Fase 3: fluxo de desligamento de responsável usa bulk reassign com `dry_run` obrigatório.
- Fase 4: remover completamente chamadas legadas de settings.
