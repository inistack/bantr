"""DEV ONLY: print a JWT for an email, creating the user if needed."""
import sys

from sqlalchemy import select

from app import create_app
from app.auth.tokens import issue_token
from app.extensions import db
from app.models import User

email = sys.argv[1].lower()
app = create_app()
with app.app_context():
    user = db.session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, name=email.split("@")[0])
        db.session.add(user)
        db.session.commit()
    print(issue_token(user.id))