# Estratégia de migração do pipeline de emissão

Status: decisão do checkpoint 1.

## Contexto

O projeto usa SQLAlchemy e declara Flask-Migrate como dependência, mas o
repositório não contém um histórico Alembic completo que demonstre a versão
atual dos bancos implantados. Criar uma revisão automática sem conhecer o
schema real pode tentar recriar tabelas existentes ou aplicar tipos PostgreSQL
incompatíveis.

## Decisão

As tabelas do pipeline são modeladas e testadas neste checkpoint, mas a
migração de homologação será gerada somente após um inventário somente-leitura
do banco de destino.

Sequência obrigatória:

1. identificar banco, schema e usuário utilizados pela homologação;
2. exportar nomes de tabelas, colunas, constraints, índices e tipos enum;
3. comparar o inventário com `db.metadata`;
4. definir e registrar uma revisão baseline para as estruturas já existentes;
5. gerar uma revisão apenas para as novas tabelas fiscais;
6. revisar manualmente o SQL de upgrade e downgrade;
7. aplicar primeiro em uma cópia ou schema descartável;
8. executar smoke tests e somente então aplicar em homologação.

## Novas estruturas esperadas

- `fiscal_certificates`
- `nfe_issuances`
- `nfe_issuance_attempts`
- `nfe_issuance_events`
- `nfe_protocols`

## Restrições

- o inventário não deve imprimir URLs com credenciais;
- nenhuma migração de produção é executada automaticamente neste checkpoint;
- homologação e produção usam schemas ou bancos distintos;
- o deploy da API não deve executar `upgrade` até existir rollback validado;
- dados e documentos reais do cliente não entram em fixtures ou migrações.

## Critério para o próximo checkpoint

O inventário do banco de homologação e a revisão baseline devem estar
disponíveis para revisão. Depois disso, a migração fiscal pode ser criada,
testada e publicada sem depender de suposições sobre o ambiente atual.
