# Histórico e auditoria

Este checkpoint adiciona um histórico imutável das principais operações em
escopos, usuários e tags de perfil.

## Preparação do banco

Antes de publicar a nova API, aplique manualmente:

```text
docs/migrations/20260929_audit_history.sql
```

A aplicação não executa a migration automaticamente.

## Eventos registrados

- criação, edição, publicação e exclusão de escopos;
- alterações em massa, agrupadas por `operation_id` mesmo quando processadas em
  vários lotes;
- criação, edição, ativação e inativação de usuários;
- mudanças de tags e de atribuições de tags.

Cada evento conserva o ator, data, organização, entidade, campos alterados e os
estados anterior e posterior. Senhas, hashes, tokens, secrets, chaves privadas e
conteúdo de certificados são removidos recursivamente antes da gravação.

O histórico começa a ser preenchido após a implantação desta versão; a migration
não fabrica eventos retroativos para alterações antigas.

## Acesso

- administradores consultam todo o histórico de sua organização;
- usuários comuns consultam somente eventos de escopos que podem acessar;
- eventos administrativos de usuários e tags não são expostos a usuários comuns;
- somente administradores podem executar reversões.

## Reversão

As ações `scope.updated` e `scope.bulk_updated` podem ser revertidas. A reversão:

1. verifica cada escopo novamente;
2. ignora registros alterados após o evento original;
3. exige a confirmação literal `REVERTER`;
4. cria uma nova operação de auditoria;
5. cria uma nova `ScopeVersion` quando o escopo é publicado;
6. nunca apaga ou reescreve o evento original.

Criação, publicação, exclusão, usuários e tags são inicialmente apenas
auditáveis. Isso evita reativação, republicação ou recriação automática sem uma
regra de negócio específica.
