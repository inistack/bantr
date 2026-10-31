import re
import time
import uuid

import structlog
from flask import g, request
from app import metrics

log = structlog.get_logger("http")

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_QUIET_PATHS = {"/health", "/metrics"} 


def init_request_logging(app):
    @app.before_request
    def _start_request():
        incoming = request.headers.get("X-Request-ID", "")
        g.request_id = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex
        g.request_started = time.perf_counter()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=g.request_id)

    @app.after_request
    def _finish_request(response):
        started = getattr(g, "request_started", None)
        elapsed = time.perf_counter() - started if started else None
        response.headers["X-Request-ID"] = getattr(g, "request_id", "-")
        user = getattr(g, "current_user", None)
        quiet = request.path in _QUIET_PATHS
        (log.debug if quiet else log.info)(
            "http.request",
            method=request.method,
            path=request.path,
            status=response.status_code,
            duration_ms=round(elapsed * 1000, 1) if elapsed is not None else None,
            user_id=str(user.id) if user else None,
        )
        if not quiet and elapsed is not None:
            route = request.url_rule.rule if request.url_rule else "unmatched"
            metrics.HTTP_REQUESTS.labels(request.method, route, str(response.status_code)).inc()
            metrics.HTTP_LATENCY.labels(route).observe(elapsed)
        return response

    @app.teardown_request
    def _end_request(exc):
        structlog.contextvars.clear_contextvars()