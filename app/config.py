import os
from sqlalchemy.engine import URL

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
INSTANCE_CONNECTION_NAME = os.getenv("INSTANCE_CONNECTION_NAME")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    print("[DB] INSTANCE_CONNECTION_NAME =", repr(INSTANCE_CONNECTION_NAME))
    print("[DB] DB_HOST =", repr(DB_HOST))
    print("[DB] DB_NAME =", repr(DB_NAME))

    if INSTANCE_CONNECTION_NAME:
        print("[DB] MODO = CLOUDSQL_SOCKET")
        # Cloud Run + Cloud SQL via Unix socket
        SQLALCHEMY_DATABASE_URI = URL.create(
            drivername="postgresql+psycopg2",
            username=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            query={
                "host": f"/cloudsql/{INSTANCE_CONNECTION_NAME}"
            }
        )
    else:
        print("[DB] MODO = TCP")
        # Ambiente local / conexão TCP direta
        SQLALCHEMY_DATABASE_URI = URL.create(
            drivername="postgresql+psycopg2",
            username=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME
        )

    JWT_ACCESS_EXPIRES_SECONDS = int(os.getenv("JWT_ACCESS_EXPIRES_SECONDS", "3600"))
    JWT_REFRESH_EXPIRES_SECONDS = int(os.getenv("JWT_REFRESH_EXPIRES_SECONDS", "604800"))