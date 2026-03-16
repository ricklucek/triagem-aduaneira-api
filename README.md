## Triagem Aduaneira API (Flask)

Backend Flask em Python 3 para atender o contrato de rotas do frontend (auth, scopes, dashboards e users), com PostgreSQL, SQLAlchemy, schemas automáticos (marshmallow-sqlalchemy) e versionamento via Alembic (Flask-Migrate).

### Stack
- Flask
- Flask-SQLAlchemy
- marshmallow + marshmallow-sqlalchemy (`SQLAlchemyAutoSchema`)
- Flask-Migrate (Alembic)
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

### Endpoints implementados
- `POST /auth/login`
- `POST /auth/bootstrap-admin` (cria primeiro admin com `email` e `password`)
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- `POST /scopes`
- `GET /scopes`
- `GET /scopes/<scopeId>`
- `PUT /scopes/<scopeId>/draft`
- `POST /scopes/<scopeId>/publish`
- `GET /scopes/<scopeId>/versions`
- `GET /dashboards/admin`
- `GET /dashboards/comercial`
- `GET /dashboards/credenciamento`
- `GET /dashboards/operacao`
- `GET /users`
- `POST /users`

- `POST /scopes` agora inicializa o `draft` com estrutura completa/default para compatibilidade com o schema do frontend.

### Segurança de rotas
- `auth_required`: valida Bearer token JWT e usuário ativo.
- `roles_required(*roles)`: aplica autorização por perfil para recursos privados (ex.: admin em `/users`).