import os
from app import create_app
from app.extensions import socketio

app = create_app()

if __name__ == '__main__':
    debug = os.environ.get("APP_DEBUG", "1") == "1"
    socketio.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "5000")),
        debug=debug,
        use_reloader=debug,
        allow_unsafe_werkzeug=True,  
    )