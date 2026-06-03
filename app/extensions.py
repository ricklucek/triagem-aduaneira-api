Base = None

def gerar_objeto_database_flask():
    """Retorna o objeto Flask-SQLAlchemy para interação com o banco 
    de dados e configura a classe base das models para ser compatível 
    com o Flask."""

    global Base

    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()

    Base = db.Model

    return db

db = gerar_objeto_database_flask()