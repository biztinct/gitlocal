"""Credential encryption adapted from Health19 channel_crypto (LGPL-3).

Original: I Am Dream Catcher Ltd. Independent Payobook key derivation; no
Health19 credentials or key material are reused. No plaintext fallback.
"""
import base64
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def _key(env):
    root = env['ir.config_parameter'].sudo().get_param('database.secret')
    if not root:
        raise ValueError('Database encryption key is missing')
    return HKDF(algorithm=hashes.SHA256(), length=32,
                salt=b'payobook-hiring', info=b'connections-v1').derive(root.encode())


def encrypt(env, value):
    nonce = os.urandom(12)
    encrypted = AESGCM(_key(env)).encrypt(nonce, value.encode(), None)
    return base64.b64encode(nonce + encrypted).decode()


def decrypt(env, value):
    if not value:
        return '{}'
    raw = base64.b64decode(value, validate=True)
    return AESGCM(_key(env)).decrypt(raw[:12], raw[12:], None).decode()
