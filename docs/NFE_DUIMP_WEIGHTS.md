# Checkpoint 4F — Pesos da DUIMP

O rascunho da NF-e utiliza somente pesos explicitamente recuperados da DUIMP.
Não há estimativa do peso bruto a partir do peso líquido.

## Preenchimento automático

- `net_weight`: soma de `pesoLiquido` dos itens da DUIMP;
- `gross_weight`: totalizador de peso bruto da carga, quando disponível;
- carga aérea ou rodoviária: usa primeiro
  `resumoRUC.totalPesoBrutoKgRecepcionados` e, na ausência, o peso entregue;
- múltiplos conhecimentos: usa o totalizador oficial ou soma somente quando a
  carga principal e todas as cargas referenciadas possuem peso bruto;
- se alguma carga referenciada não possuir peso, o campo bruto permanece vazio
  para evitar um total parcial.

Snapshots criados antes do 4F são complementados em memória a partir do
`raw_payload`; o registro histórico original não é reescrito.

As origens ficam persistidas em `fiscal_payload.transport.volume`:

- `duimp_items`;
- `duimp_cargo_total`;
- `duimp_cargo_received`;
- `duimp_cargo_delivered`;
- `duimp_cargo_totalized`;
- `tax_rule_default`;
- `operator_override`.

## Precedência

1. ajuste informado pelo operador;
2. peso específico da DUIMP atual;
3. valor padrão da regra tributária, apenas como fallback;
4. campo vazio quando nenhuma origem confiável existir.

Ao enviar `null` em `net_weight` ou `gross_weight` pelo
`PATCH /nfe-drafts/{draft_id}`, a API remove o ajuste manual daquele campo e
restaura o valor automático disponível.

## Diagnósticos

Quando os dois pesos estão presentes e o líquido é maior que o bruto, a
validação inclui o aviso `net_weight_exceeds_gross_weight`. O diagnóstico não
altera os valores informados.

Este checkpoint não altera models ou tabelas e não exige migration.
