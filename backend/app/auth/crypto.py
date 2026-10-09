from cryptography.fernet import Fernet
from flask import current_app

def _fernet():
    return Fernet(current_app.config['TOKEN_ENCRYPTION_KEY'])


def encrypt(value):
    return _fernet().encrypt(value.encode()).decode() if value else None

def decrypt(value):
    return _fernet().decrypt(value.encode()).decode() if value else None
