import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/triagem"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_ACCESS_EXPIRES_SECONDS = int(os.getenv("JWT_ACCESS_EXPIRES_SECONDS", "3600"))
    JWT_REFRESH_EXPIRES_SECONDS = int(os.getenv("JWT_REFRESH_EXPIRES_SECONDS", "604800"))