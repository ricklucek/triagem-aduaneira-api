# Inativação de escopos

## Publicação

1. Execute `docs/migrations/20261026_scope_deactivation.sql` no banco do ambiente, antes de implantar a API. A migration é transacional e pode ser reaplicada. Ela acrescenta três colunas opcionais, preservando os registros existentes.
2. Integre e publique a API.
3. Integre e publique o front-end correspondente.

O repositório mantém migrations SQL em `docs/migrations`; esta entrega segue esse padrão. Não execute `alembic upgrade` para esta alteração.

## Contrato

| Requisição | Resultado |
| --- | --- |
| `POST /scopes/{id}/deactivate` | Inativa um rascunho ou publicado; requer administrador da mesma organização. |
| `POST /scopes/{id}/reactivate` | Restaura o estado anterior; requer a mesma permissão. |
| `GET /scopes?activity=active` | Lista somente escopos ativos; comportamento padrão. |
| `GET /scopes?activity=inactive` | Consulta inativos; somente administradores. |
| `GET /scopes?activity=all` | Consulta todos os estados; somente administradores. |
| `GET /scopes?status=archived` | Compatibilidade com o filtro de status existente; somente administradores. |

Os filtros existentes (busca, cliente, responsáveis, paginação, `status` e `include_drafts`) continuam disponíveis. `include_drafts=true` não deve incluir inativos em uma consulta de ativos. Na interface, “Todos” inclui também rascunhos; em “Ativos” permanece a opção “Incluir rascunhos”. A visibilidade de rascunhos continua restrita ao autor e admins; quando listados para outras pessoas, somente seu resumo é mostrado com `can_view=false`.

O estado persistido é `archived`, apresentado como **Inativo**. São registrados `archived_from_status`, `archived_at` (UTC) e `archived_by_id`. Ao reativar, esses campos são limpos; o histórico conserva os registros anteriores. Escopos legados arquivados sem estado anterior voltam como rascunho, evitando publicação implícita.

As ações preservam JSONs, versões, responsáveis e o vínculo com o cliente. Não criam uma versão de publicação nem mudam o status do cliente. A restrição de um escopo por cliente permanece. Repetir a mesma ação não duplica eventos de auditoria.

Escopos inativos podem ser consultados e ter suas versões acessadas por admins. A API rejeita edição, publicação, sincronização e exclusão com `409 scope_inactive`. Sincronizações em lote, métricas e alterações em massa excluem inativos. A reversão de histórico não reativa nem altera um escopo inativo. As operações individuais de escrita usam bloqueio da linha para serializar mudanças concorrentes.

A política inicial está em `app/scope_permissions.py::can_manage_scope_lifecycle`, para permitir expansão futura. Ocultar o botão no front-end não substitui a autorização da API.

## Validação

Execute os testes de integração de ciclo de vida, clientes, alterações em massa, histórico e dashboards. Na plataforma:

1. Como admin, inative um publicado e um rascunho e confirme sua saída da lista de ativos.
2. Consulte **Inativos**, abra o documento e faça download. A página de edição deve apresentar um aviso com acesso à consulta.
3. Reative e confirme o retorno ao estado anterior, sem alteração de conteúdo ou versão.
4. Confira os eventos “Escopo inativado” e “Escopo reativado” no histórico.
5. Como usuário comum, confirme que os botões e filtros de inativos não aparecem e que a API rejeita as ações mesmo usando os IDs diretamente.
