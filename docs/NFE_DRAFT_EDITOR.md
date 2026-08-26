# Checkpoint 4E — Editor auditável do rascunho

## Alterações de banco necessárias

O projeto não contém nem executa migrations. Antes de usar o checkpoint, o
ambiente responsável pelo banco deve adicionar a `nfe_drafts`:

- `deleted_at` (`timestamp`, nulo, indexado);
- `deleted_by_user_id` (`uuid`, nulo, FK para `users.id`, indexado);
- `deletion_reason` (`text`, nulo);
- `deletion_mode` (`varchar(20)`, nulo; valores usados: `deleted` e `archived`).

Nenhum upgrade Alembic é disparado pela aplicação.

## Contratos principais

- `PATCH /nfe-drafts/{draft_id}` atualiza metadados e também aceita
  `additional_costs`; despesas provocam novo rateio, recálculo de totais e
  reconciliação.
- `PATCH /nfe-drafts/{draft_id}/items/{item_id}` altera dados comerciais do
  item, mas não aceita mais substituir `tax_payload` diretamente.
- `PATCH /nfe-drafts/{draft_id}/items/{item_id}/tax-adjustment` aplica ajuste
  manual auditado ou reaplica a regra tributária vinculada.
- `DELETE /nfe-drafts/{draft_id}` e
  `POST /nfe-drafts/{draft_id}/remove` executam a mesma remoção lógica.

O ajuste tributário exige motivo com 10 a 500 caracteres. O histórico fica no
`tax_payload.icms.adjustment_history`, incluindo valores anteriores/novos,
usuário, data e origem do cálculo.

## Exclusão e arquivamento

- Sem número, chave ou XML: `deletion_mode=deleted`.
- Com número, chave ou XML não assinado: `deletion_mode=archived` e
  `fiscal_payload.numbering_disposition.status=pending_inutilization_review`.
- Assinado, transmitido, autorizado ou cancelado: operação rejeitada.

Rascunhos removidos deixam de participar do fluxo ativo e da geração de XML,
mas continuam retornados no histórico do processo para auditoria.
