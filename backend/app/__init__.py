import os
import structlog

from flask import Flask, jsonify, request
from app.errors import AppError

from app.config import config_by_name
from app.extensions import db, migrate,socketio
from app.rate_limit import rate_limit_key


def create_app(config_name=None):
    config_name = config_name or os.environ.get("APP_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])
    from app.logging_config import configure_logging
    configure_logging(app.config["LOG_FORMAT"], app.config["LOG_LEVEL"])

    from app.request_logging import init_request_logging
    init_request_logging(app)



    db.init_app(app)
    migrate.init_app(app, db)
    from app.auth.oauth import init_oauth
    init_oauth(app)
    from app.redis_client import init_redis
    init_redis(app)

    from app.models import User, OAuthAccount  
    socketio.init_app(
        app, async_mode='threading', cors_allowed_origins=app.config.get("SOCKETIO_CORS_ORIGINS"), 
        message_queue=app.config["REDIS_URL"], logger=False
    )
    from app.rate_limit import limiter
    limiter.init_app(app)

    from app.sockets import connection
    from app.sockets import channels as socket_channels

    from app.api.health import health_bp
    from app.api.auth import auth_bp
    from app.api.workspaces import workspace_bp
    from app.api.channels import channel_bp
    from app.api.messages import message_bp
    from app.errors import AppError
    from flask import jsonify

    @app.errorhandler(AppError)
    def handle_app_error(err):
        return jsonify(error=err.message), err.status_code
    
    @app.errorhandler(429)
    def handle_rate_limit(err):
        structlog.get_logger("rate_limit").warning(
            "rate_limit.exceeded", key=rate_limit_key(), limit=str(err.description), path=request.path
        )
        return jsonify(error="Too many requests. Slow down and retry shortly.", limit=str(err.description)), 429
    
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(workspace_bp)
    app.register_blueprint(channel_bp)
    app.register_blueprint(message_bp)

    return app

