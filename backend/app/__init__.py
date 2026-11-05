import os

import structlog
from flask import Flask, jsonify, request

from app.config import config_by_name
from app.errors import AppError
from app.extensions import db, migrate, socketio
from app.rate_limit import rate_limit_key


def create_app(config_name=None):
    config_name = config_name or os.environ.get("APP_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    if config_name == "production":
        from app.config import missing_production_settings

        problems = missing_production_settings(app.config)
        if problems:
            raise RuntimeError("Refusing to start in production. Fix: " + ", ".join(problems))

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

    socketio.init_app(
        app,
        async_mode=app.config["SOCKETIO_ASYNC_MODE"],
        cors_allowed_origins=app.config.get("SOCKETIO_CORS_ORIGINS"),
        message_queue=app.config["REDIS_URL"],
        channel=app.config["SOCKETIO_CHANNEL"],
        logger=False,
    )
    from app.rate_limit import limiter

    limiter.init_app(app)

    from app.api.auth import auth_bp
    from app.api.channels import channel_bp
    from app.api.health import health_bp
    from app.api.messages import message_bp
    from app.api.metrics import bp as metrics_bp
    from app.api.workspaces import workspace_bp
    from app.sockets import channels as socket_channels  # noqa: F401
    from app.sockets import connection  # noqa: F401

    @app.errorhandler(AppError)
    def handle_app_error(err):
        return jsonify(error=err.message), err.status_code

    @app.errorhandler(429)
    def handle_rate_limit(err):
        structlog.get_logger("rate_limit").warning(
            "rate_limit.exceeded",
            key=rate_limit_key(),
            limit=str(err.description),
            path=request.path,
        )
        return jsonify(
            error="Too many requests. Slow down and retry shortly.", limit=str(err.description)
        ), 429

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(workspace_bp)
    app.register_blueprint(channel_bp)
    app.register_blueprint(message_bp)
    app.register_blueprint(metrics_bp)

    if app.config["PROXY_HOPS"]:
        from werkzeug.middleware.proxy_fix import ProxyFix

        hops = app.config["PROXY_HOPS"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops)

    return app
