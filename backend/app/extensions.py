from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
from flask_socketio import SocketIO

db = SQLAlchemy()
migrate = Migrate()
oauth = OAuth()
socketio = SocketIO()