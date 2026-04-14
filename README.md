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

### Executar API
```bash
flask --app wsgi.py run --host 0.0.0.0 --port 5000
```

### Documentação
- Endpoints: `docs/ENDPOINTS.md`
- Contexto da transformação backend/frontend: `docs/BACKEND_TRANSFORMATION.md`
