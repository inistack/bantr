import requests
from authlib.integrations.base_client import OAuthError
from flask import Blueprint, current_app, g, jsonify, redirect, request, url_for
from sqlalchemy import select

from app.auth.decorators import COOKIE_NAME, login_required
from app.auth.tokens import issue_token
from app.errors import BadRequest, NotFound
from app.extensions import db, oauth
from app.models import User
from app.services.auth_service import login_with_oauth

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _login_response(response, user):
    response.set_cookie(
        COOKIE_NAME,
        issue_token(user.id),
        httponly=True,
        samesite="Lax",
        secure=current_app.config["COOKIE_SECURE"],
        max_age=current_app.config["JWT_EXPIRES_MINUTES"] * 60,
    )
    return response


def _to_frontend(query=""):
    return redirect(current_app.config["FRONTEND_URL"] + query)


@auth_bp.get("/github/login")
def github_login():
    redirect_uri = url_for("auth.github_callback", _external=True)
    return oauth.github.authorize_redirect(redirect_uri)


@auth_bp.get("/github/callback")
def github_callback():
    try:
        token = oauth.github.authorize_access_token()
        user_resp = oauth.github.get("user", token=token, timeout=10)
        user_resp.raise_for_status()
        emails_resp = oauth.github.get("user/emails", token=token, timeout=10)
        emails_resp.raise_for_status()
    except (OAuthError, requests.RequestException):
        current_app.logger.exception("GitHub OAuth failed")
        return _to_frontend("?login_error=provider")

    profile, emails = user_resp.json(), emails_resp.json()
    verified = [e["email"] for e in emails if e["verified"]]
    primary = next(
        (e["email"] for e in emails if e["primary"] and e["verified"]),
        verified[0] if verified else None,
    )
    if primary is None:
        return _to_frontend("?login_error=no_verified_email")

    user = login_with_oauth(
        provider="github",
        provider_user_id=str(profile["id"]),
        email=primary,
        name=profile.get("name") or profile["login"],
        avatar_url=profile.get("avatar_url"),
        token=token,
    )
    return _login_response(_to_frontend(), user)


@auth_bp.get("/me")
@login_required
def me():
    user = g.current_user
    return jsonify(id=str(user.id), email=user.email, name=user.name, avatar_url=user.avatar_url)


@auth_bp.post("/logout")
@login_required
def logout():
    resp = jsonify(status="logged out")
    resp.delete_cookie(COOKIE_NAME)
    return resp


@auth_bp.post("/dev-login")
def dev_login():
    """DEVELOPMENT ONLY: sign in as any email without OAuth. Does not exist unless enabled."""
    if not current_app.config["DEV_LOGIN_ENABLED"]:
        raise NotFound("Not found")
    email = ((request.get_json(silent=True) or {}).get("email") or "").strip().lower()
    if "@" not in email:
        raise BadRequest("email is required")
    user = db.session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, name=email.split("@")[0])
        db.session.add(user)
        db.session.commit()
    return _login_response(jsonify(id=str(user.id), email=user.email, name=user.name), user)
