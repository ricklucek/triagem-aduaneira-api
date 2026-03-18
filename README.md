## Triagem Aduaneira API (Flask)

Backend Flask em Python 3 para atender o contrato do frontend com autenticação JWT, PostgreSQL, SQLAlchemy e versionamento via Flask-Migrate/Alembic.

### Stack
- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- marshmallow + marshmallow-sqlalchemy
- PostgreSQL
- JWT (access + refresh)

### Configuração
1. Criar ambiente virtual e instalar dependências:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Configurar variáveis de ambiente:
   ```bash
   export DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/triagem
   export SECRET_KEY=uma-chave-secreta-forte
   export JWT_ACCESS_EXPIRES_SECONDS=3600
   export JWT_REFRESH_EXPIRES_SECONDS=604800
   ```

### Migrations (Alembic)
```bash
flask --app wsgi.py db init
flask --app wsgi.py db migrate -m "initial schema"
flask --app wsgi.py db upgrade
```

### Executar API
```bash
flask --app wsgi.py run --host 0.0.0.0 --port 5000
```

### Regras implementadas
- Admins ficam em tabela separada (`admins`) e sempre possuem privilégios administrativos.
- Usuários operacionais ficam em `users` com `role`/`setor` específicos.
- As informações fixas do escopo (`salarioMinimoVigente` e `dadosBancariosCasco`) são mantidas pelo admin e injetadas automaticamente no `draft` do escopo.
- Responsáveis do formulário são carregados a partir dos usuários cadastrados, removendo dependência de listas hardcoded no frontend.

### Endpoints
#### Auth
- `POST /auth/bootstrap-admin`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`

#### Admin
- `GET /admin/settings`
- `PUT /admin/settings`

#### Usuários
- `GET /users` (admin)
- `POST /users` (admin)
- `DELETE /users/<userId>` (admin, desativa usuário)
- `GET /users/responsibles` (autenticado)

#### Escopos
- `GET /scopes/metadata`
- `POST /scopes`
- `GET /scopes`
- `GET /scopes/<scopeId>`
- `PUT /scopes/<scopeId>/draft`
- `POST /scopes/<scopeId>/publish`
- `GET /scopes/<scopeId>/versions`

#### Dashboards
- `GET /dashboards/admin`
- `GET /dashboards/comercial`
- `GET /dashboards/credenciamento`
- `GET /dashboards/operacao`

### Segurança de rotas
- `auth_required`: valida Bearer token JWT e resolve se o principal autenticado é um `Admin` ou `User`.
- `admin_required`: restringe acesso apenas para principals da tabela `admins`.
- `roles_required(*roles)`: permite admins e, para usuários operacionais, valida o `role` exigido.