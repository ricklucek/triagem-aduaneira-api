# Dashboard por tags de perfil

Este checkpoint conecta as tags operacionais dos usuários às consultas do
dashboard, sem alterar as atribuições registradas nos escopos.

## Semântica do filtro

O parâmetro opcional é aceito como `tagId` ou `tag_id`. Um escopo corresponde à
tag quando pelo menos uma destas relações pertence a um usuário com a tag:

- criador do escopo;
- responsável principal (`responsible_user_id`);
- atribuição ativa em `scope_assignments`.

Nas visões agrupadas por usuário, a pessoa exibida também precisa possuir a tag
selecionada. Isso impede que um usuário sem a tag apareça apenas porque outro
participante do mesmo escopo a possui.

O filtro é aplicado aos endpoints:

- `GET /dashboards/admin/metrics`;
- `GET /dashboards/admin/scopes-by-user`;
- `GET /dashboards/admin/users/<user_id>/scopes`;
- `GET /dashboards/admin/clients-by-user`;
- `GET /dashboards/admin/users/<user_id>/clients`;
- `GET /dashboards/admin/services`;
- `GET /dashboards/admin/services/by-scope`.

As respostas agrupadas incluem `userTags`, permitindo identificar visualmente
as funções operacionais sem inferi-las pelo papel técnico de acesso.

## Visibilidade de rascunhos

As consultas do dashboard aplicam a mesma regra do restante da plataforma:

- administradores podem consultar todos os escopos da organização;
- usuários não administradores consultam escopos publicados e os próprios
  rascunhos;
- rascunhos de outros autores nunca são agregados ou listados.

O isolamento por `organization_id` permanece obrigatório, inclusive quando um
`tagId` válido de outra organização é informado.

## Banco de dados

Esta etapa reutiliza `user_tags`, `user_tag_assignments` e
`scope_assignments`. Não há nova migration.
