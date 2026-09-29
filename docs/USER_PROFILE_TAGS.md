# Tags de perfil dos usuários

Este checkpoint separa dois conceitos que antes estavam misturados:

- `users.role` continua sendo a fonte de autorização técnica;
- tags representam funções operacionais e podem ser usadas em filtros,
  seletores e atribuições futuras.

As tags padrão são `Admin`, `Comercial`, `Analista DA`, `Analista AE`,
`Credenciamento` e `Operação`. Administradores podem criar outras tags para a
própria organização.

## Regra da tag Admin

`Admin` é uma tag mestre. Ao atribuí-la, as demais tags do usuário são
removidas e o nível de acesso passa a `admin`. Ao removê-la, a requisição deve
informar explicitamente um nível de acesso não administrativo.

O backend também impede:

- inativar a tag mestre;
- inativar o próprio usuário;
- remover ou inativar o último administrador ativo da organização;
- atribuir tags inativas ou pertencentes a outra organização.

## Implantação

Esta entrega adiciona tabelas e exige migration. Faça backup do banco e execute
antes da publicação da nova versão da API:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f docs/migrations/20260929_user_profile_tags.sql
```

O PostgreSQL precisa disponibilizar `gen_random_uuid()`. Em instalações sem a
função, habilite previamente a extensão `pgcrypto` com uma conta autorizada.

A migration:

1. cria `user_tags` e `user_tag_assignments`;
2. cria as seis tags padrão em cada organização;
3. normaliza o papel legado `administrador` para `admin`;
4. associa usuários existentes à tag equivalente ao seu nível atual;
5. classifica papéis sem correspondência como `Operação` sem alterar seu
   histórico de usuário.

Depois da aplicação, valide:

```sql
SELECT organization_id, code, name, is_master, active
FROM user_tags
ORDER BY organization_id, is_master DESC, name;

SELECT u.email, u.role, t.code
FROM users u
LEFT JOIN user_tag_assignments uta ON uta.user_id = u.id
LEFT JOIN user_tags t ON t.id = uta.tag_id
ORDER BY u.email, t.code;
```

## Compatibilidade

O endpoint de responsáveis continua fornecendo `id`, `nome`, `email`, `role` e
`setor`, acrescentando apenas os metadados e as tags. Usuários são inativados,
não excluídos, para preservar vínculos históricos.

As tags desta etapa ainda não substituem os papéis específicos de atribuição
dos escopos. Essa migração será feita no checkpoint do novo fluxo de alteração
em massa, depois que os filtros de dashboard estiverem estabilizados.
