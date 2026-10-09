import requests
from authlib.integrations.base_client import OAuthError
from flask import jsonify, url_for, current_app, Blueprint
from app.extensions import oauth
from app.services.auth_service import login_with_oauth
from flask import g
from app.auth.decorators import COOKIE_NAME, login_required
from app.auth.tokens import issue_token

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.get('/github/login')
def github_login():
    redirect_uri = url_for('auth.github_callback', _external=True)
    return oauth.github.authorize_redirect(redirect_uri)


@auth_bp.get('/github/callback')
def github_callback():
    try:
        token = oauth.github.authorize_access_token()
        user_resp = oauth.github.get('user', token=token, timeout=10)
        user_resp.raise_for_status()
        emails_resp = oauth.github.get("user/emails", token=token, timeout=10)
        emails_resp.raise_for_status()
    except (OAuthError, requests.RequestException):
        current_app.logger.exception("GitHub OAuth failed")
        return jsonify(error="Could not complete login with GitHub"), 502
    
    profile = user_resp.json()
    verified = [e["email"] for e in emails_resp.json() if e["verified"]]
    primary = next(
        (e["email"] for e in emails_resp.json() if e["primary"] and e["verified"]),
        verified[0] if verified else None,
    )

    if primary is None:
        return jsonify(error="Your GitHub account has no verified email"), 400
    
    user = login_with_oauth(
        provider="github",
        provider_user_id=str(profile["id"]),
        email=primary,
        name=profile.get("name") or profile["login"],
        avatar_url=profile.get("avatar_url"),
        token=token,
    )
    token = issue_token(user.id)
    resp = jsonify(id=str(user.id), email=user.email, name=user.name)
    resp.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="Lax",
        secure=current_app.config["COOKIE_SECURE"],
        max_age=current_app.config["JWT_EXPIRES_MINUTES"] * 60,
    )
    return resp

@auth_bp.get('/me')
@login_required
def me():
    user = g.current_user
    return jsonify(
        id=str(user.id), email=user.email, name=user.name, avatar_url=user.avatar_url
    )


@auth_bp.post('/logout')
@login_required
def logout():
    resp = jsonify(status="logged out")
    resp.delete_cookie(COOKIE_NAME)
    return resp