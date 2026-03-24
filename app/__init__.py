from flask import Flask, jsonify
from flask_cors import CORS
from marshmallow import ValidationError

from .config import Config
from .extensions import db
from .routes.auth_routes import auth_bp
from .routes.dashboard_routes import dashboard_bp
from .routes.scope_routes import scope_bp
from .routes.user_routes import user_bp
from .routes.admin_routes import admin_bp
from .routes.prepostos import prepostos_bp


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    CORS(
        app,
        resources={r"/*": {"origins": "https://triagem-aduaneira.vercel.app"}},
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )

    db.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(scope_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(prepostos_bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.errorhandler(ValidationError)
    def handle_validation_error(err):
        return jsonify({"error": "Validation error", "messages": err.messages}), 400

    return app