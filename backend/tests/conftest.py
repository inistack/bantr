from types import SimpleNamespace

import pytest
from sqlalchemy import text

from app import create_app
from app.auth.tokens import issue_token
from app.extensions import db
from app.models import User

