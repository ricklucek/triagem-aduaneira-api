# Plano de integração da NF-e via DUIMP no front-end

## Objetivo

Integrar a emissão diagnóstica de NF-e de importação ao repositório
`ricklucek/triagem-aduaneira`, partindo da branch `main`, com uma jornada curta,
auditável e orientada por pendências. A interface deve reutilizar cadastros e
regras fiscais do cliente e solicitar ao operador somente dados ausentes ou
específicos daquela operação.

A assinatura e a transmissão à SEFAZ permanecem fora do primeiro checkpoint do
front-end. O resultado inicial será a chave de acesso, o XML não assinado e a
validação XSD.

## Estratégia de branch

1. Atualizar a `main` do front-end.
2. Criar `feat/nfe-issuance-wizard` a partir da `main` atualizada.
3. Integrar primeiro os contratos da API e a jornada diagnóstica.
4. Abrir PR independente para revisão de UX e regras operacionais.
5. Tratar assinatura e transmissão em outra branch, após homologação fiscal.

## Jornada proposta

### 1. Cliente e DUIMP

O operador seleciona o cliente e informa somente o número da DUIMP. A tela
verifica automaticamente:

- perfil fiscal padrão;
- regra tributária aplicável;
- sequência numérica de homologação;
- situação do cliente;
- existência de processo anterior para a mesma DUIMP.

Se o cliente não existir, a interface abre um cadastro rápido e retorna ao fluxo
sem perder o número digitado.

Chamadas:

1. `GET /clients/{client_id}`
2. `GET /clients/{client_id}/fiscal-profile`
3. `GET /clients/{client_id}/import-tax-rules`
4. `GET /clients/{client_id}/nfe-number-sequences`
5. `POST /import-processes`
6. `POST /import-processes/{process_id}/duimp/fetch`

### 2. Contexto automático

Após o fetch, o front-end chama `nfe-context` e apresenta apenas as pendências.
Campos obtidos do Portal Único ficam identificados como automáticos. Overrides
do operador devem exibir a fonte e ficar registrados no contexto persistido.

Chamadas:

1. `GET /import-processes/{process_id}/nfe-context`
2. `POST /import-processes/{process_id}/nfe-context/resolve`

O botão **Continuar** fica bloqueado somente quando `ready_for_draft=false`.

### 3. Revisão da operação

A tela apresenta um resumo, não o XML:

- emitente e fornecedor estrangeiro;
- finalidade e modalidade;
- desembaraço;
- quantidade de itens;
- produtos, NCM, CFOP e CEST;
- tributos e custos adicionais;
- transporte e volumes;
- natureza da operação e informações complementares.

Defaults devem vir da regra fiscal. O operador altera somente exceções.

Payload recomendado:

```json
{
  "environment": "homologation",
  "series": "1",
  "import_purpose": "resale",
  "duimp_snapshot_id": "UUID",
  "document": {
    "operation_nature": "Compra para comercialização",
    "presence_indicator": "9",
    "intermediary_indicator": "0"
  },
  "item_defaults": {
    "commercial_unit": "PCE",
    "taxable_unit": "UN"
  },
  "additional_costs": {},
  "transport": {},
  "additional_info": {}
}
```

Chamada:

`POST /import-processes/{process_id}/nfe-draft/from-duimp`

### 4. Validação e correções

Após criar o draft, a tela chama:

`POST /nfe-drafts/{draft_id}/validate`

Os retornos devem ser agrupados em três níveis:

| Nível | Comportamento |
|---|---|
| Erro | Bloqueia chave e XML; leva o usuário ao campo correspondente. |
| Aviso fiscal | Permite XML diagnóstico, mas mantém assinatura/transmissão bloqueadas. |
| Sugestão operacional | Permite continuar; recomenda completar transporte, volumes ou texto legal. |

Cada mensagem deve usar `field` para focar a seção e `code` para escolher título,
ícone e ação. Exemplos:

- `missing_transport_carrier`;
- `incomplete_transport_volume`;
- `missing_fiscal_legal_text`;
- `missing_nominal_icms_rate`;
- `diagnostic_icms_reconciliation_difference`;
- `unconfirmed_icms_tax_treatment`.

Dados gerais e itens podem ser corrigidos sem recriar o processo:

`PATCH /nfe-drafts/{draft_id}`

`PATCH /nfe-drafts/{draft_id}/items/{item_id}`

O primeiro endpoint aceita natureza/indicadores, unidades padrão, transporte,
pagamento e informações adicionais. Se já existir XML, a resposta devolve
`requires_new_xml=true`; a versão anterior continua preservada para auditoria e
o front-end deve oferecer a geração de uma nova versão. Depois de cada correção,
o front-end repete a validação sem recriar o processo.

### 5. Confirmação e XML

O número da NF-e somente deve ser reservado quando o usuário clicar em
**Confirmar e gerar XML**. A interface mostra antes um resumo final dos totais,
avisos e ambiente.

Chamadas:

1. `POST /nfe-drafts/{draft_id}/generate-access-key`
2. `POST /nfe-drafts/{draft_id}/generate-xml`
3. `POST /nfe-drafts/{draft_id}/xml-versions/{version_id}/validate-xsd`
4. `GET /nfe-drafts/{draft_id}/xml-versions/{version_id}/download`

O resultado deve mostrar:

- ambiente em destaque;
- número, série e chave;
- resultado do XSD;
- botão de download;
- lista dos avisos mantidos;
- indicação explícita de que o XML não foi assinado nem transmitido.

## Automações

- Normalizar o número da DUIMP digitado.
- Reaproveitar processo/snapshot existente quando a API indicar idempotência.
- Selecionar perfil fiscal padrão e regra tributária por cliente, UF, finalidade,
  modalidade, NCM e vigência.
- Preencher custos disponíveis no Portal Único.
- Calcular peso líquido pela soma dos itens.
- Gerar resumo fiscal para `infCpl`.
- Aplicar natureza, indicadores, unidades, transportadora e texto legal da regra.
- Aplicar `cFabricante=0000` apenas no fallback controlado já auditado.
- Salvar as escolhas do operador no draft, sem alterar automaticamente o cadastro
  permanente do cliente.

## Componentes sugeridos

- `NfeIssuanceWizard` — controla etapas e restauração do processo.
- `DuimpLookupStep` — cliente, número e consulta.
- `NfeContextStep` — pendências e fontes dos dados.
- `NfeReviewStep` — itens, custos, transporte e textos.
- `NfeValidationPanel` — erros, avisos e sugestões acionáveis.
- `NfeGenerationStep` — confirmação, chave, XSD e download.
- `FiscalRuleBadge` — regra selecionada, vigência e modo diagnóstico/fiscal.

## Estado e recuperação

O identificador principal no navegador deve ser o `process_id`. `snapshot_id`,
`draft_id` e `xml_version_id` ficam associados a ele. Ao recarregar a página, a
interface consulta o processo e o draft, em vez de reiniciar o fluxo.

Erros HTTP não devem apagar respostas válidas anteriores. Ações de fetch,
resolve, criação do draft e geração do XML precisam impedir duplo clique e
mostrar claramente quando uma tentativa pode reservar numeração.

## Critérios de aceite do primeiro checkpoint

- Concluir uma DUIMP com perfil e regra já cadastrados em no máximo cinco telas.
- Não exigir digitação de dados já presentes na DUIMP ou na regra fiscal.
- Não reservar número antes da confirmação final.
- Permitir corrigir item e validar novamente sem recriar o processo.
- Gerar, validar no XSD e baixar o XML não assinado.
- Diferenciar visualmente erro, aviso fiscal e sugestão operacional.
- Restaurar um fluxo interrompido a partir do `process_id`.
- Bloquear assinatura/transmissão enquanto `authorization.ready=false`.

## Sequência de implementação no front-end

1. Cliente, DUIMP e criação do processo.
2. Fetch, contexto e resolução de pendências.
3. Revisão e criação do draft.
4. Edição de itens e painel de validação.
5. Chave, XML, XSD e download.
6. Teste assistido com as DUIMPs já usadas na homologação.
7. Ajustes de usabilidade e abertura do PR.
