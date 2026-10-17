def _key(workspace_id):
    return f'presence:ws:{workspace_id}'


def _member(user_id, sid):
    return f'{user_id}|{sid}'