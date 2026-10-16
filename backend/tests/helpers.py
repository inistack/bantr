from app.extensions import socketio


def create_ws(client, owner, slug='acme'):
    r = client.post(
        '/workspaces', json={'name': slug.title(), 'slug': slug}, headers=owner.headers
    )
    assert r.status_code == 201
    return r.get_json()['id']


def add_member(client, actor, ws, email, role='member'):
    return client.post(
        f'/workspaces/{ws}/members',
        json={'email': email, 'role':role},
        headers=actor.headers
    )


def create_channel(client, actor, ws, name='general'):
    r = client.post(
        f'/workspaces/{ws}/channels', json={'name': name}, headers=actor.headers
    )
    assert r.status_code == 201
    return r.get_json()['id']


def send(client, actor, ws, ch, body):
    return client.post(
        f'/workspaces/{ws}/channels/{ch}/messages', json={'body': body}, headers=actor.headers
    )


def socket_connect(app, user):
    token = user.headers["Authorization"].split(" ", 1)[1]
    sio_client = socketio.test_client(app, auth={"token": token})
    assert sio_client.is_connected()
    return sio_client


def socket_join(sio_client, ws, ch):
    return sio_client.emit(
        "channel.join", {"workspace_id": ws, "channel_id": ch}, callback=True
    )