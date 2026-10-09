import os

from flask import Flask, jsonify
from app.errors import AppError

from app.config import config_by_name
from app.extensions import db, migrate


def create_app(config_name=None):
    config_name = config_name or os.environ.get("APP_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])


    db.init_app(app)
    migrate.init_app(app, db)
    from app.auth.oauth import init_oauth
    init_oauth(app)

    from app.models import User, OAuthAccount  

    from app.api.health import health_bp
    from app.api.auth import auth_bp
    from app.api.workspaces import workspace_bp
    from app.errors import AppError
    from flask import jsonify

    @app.errorhandler(AppError)
    def handle_app_error(err):
        return jsonify(error=err.message), err.status_code
    
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(workspace_bp)

    return app

