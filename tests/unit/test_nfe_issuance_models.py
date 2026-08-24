from app import create_app
from app.extensions import db


class TestConfig:
    TESTING = True
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_ACCESS_EXPIRES_SECONDS = 3600
    JWT_REFRESH_EXPIRES_SECONDS = 604800


def test_issuance_checkpoint_tables_are_registered():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        expected = {
            "fiscal_certificates",
            "nfe_issuances",
            "nfe_issuance_attempts",
            "nfe_issuance_events",
            "nfe_protocols",
        }
        assert expected.issubset(db.metadata.tables)


def test_issuance_status_is_restricted_at_database_level():
    app = create_app(TestConfig)
    with app.app_context():
        constraints = {
            constraint.name
            for constraint in db.metadata.tables["nfe_issuances"].constraints
        }
        assert "ck_nfe_issuance_status" in constraints
