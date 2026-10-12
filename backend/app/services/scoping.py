from sqlalchemy import select
from app.errors import NotFound
from app.extensions import db

def scoped_select(model, workspace_id):
    if not hasattr(model, 'workspace_id'):
        raise TypeError(f'{model.__name__} is not tenant-scoped')
    return select(model).where(model.workspace_id == workspace_id)

def get_in_workspace(model, workspace_id, obj_id):
    obj = db.session.scalar(scoped_select(model, workspace_id).where(model.id == obj_id))
    if obj is None:
        raise NotFound(f'{model.__name__} not found')
    
