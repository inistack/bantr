import sys
import socketio

token = sys.argv[1] if len(sys.argv) > 1 else None
sio = socketio.Client(logger=True, engineio_logger=True)


@sio.event
def connect():
    print("connected, sid =", sio.sid)


@sio.on('connected')
def on_connected(data):
    print('server says:', data)


@sio.event
def disconnect():
    print('disconnected')


try:
    sio.connect(
        'http://localhost:5000',
        auth={'token': token} if token else None,
        transports=['websocket']
    )
except socketio.exceptions.ConnectionError as exc:
    print('Connection refused:', exc)
    sys.exit(1)

print('whoami ->', sio.call('whoami', timeout=10))
sio.sleep(1)
sio.disconnect()
