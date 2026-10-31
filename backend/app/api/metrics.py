import hmac

from flask import Blueprint, Response, current_app, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

bp = Blueprint("metrics", __name__)


@bp.get("/metrics")
def metrics_endpoint():
    token = current_app.config.get("METRICS_TOKEN")
    if token:
        supplied = request.headers.get("Authorization", "").encode()
        if not hmac.compare_digest(supplied, f"Bearer {token}".encode()):
            return jsonify(error="Authentication required"), 401
    return Response(generate_latest(), content_type=CONTENT_TYPE_LATEST)