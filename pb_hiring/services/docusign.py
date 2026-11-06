"""Small, bounded client for the official DocuSign eSignature v2.1 API.

OAuth JWT uses the already-required cryptography library. No signing engine,
certificate authority or document rendering service runs on the Odoo host.
"""
import base64
import hashlib
import hmac
import json
import re
import time
from urllib.parse import urlsplit

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from odoo import _
from odoo.exceptions import UserError


def auth_host(environment):
    if environment not in ('demo', 'production'):
        raise UserError(_('Choose the DocuSign demo or production environment.'))
    return 'account-d.docusign.com' if environment == 'demo' else 'account.docusign.com'


def api_base(value, environment):
    parsed = urlsplit(value)
    host = parsed.hostname or ''
    if (parsed.scheme != 'https' or parsed.username or parsed.password or
            parsed.port not in (None, 443) or parsed.path not in ('', '/') or
            parsed.query or parsed.fragment or
            not re.fullmatch(r'[a-z0-9-]+\.docusign\.net', host) or
            (environment == 'demo') != (host == 'demo.docusign.net')):
        raise UserError(_('DocuSign returned an unexpected account API address.'))
    return 'https://' + host + '/restapi/v2.1'


def jwt_assertion(client_id, user_id, environment, private_key):
    encode = lambda b: base64.urlsafe_b64encode(b).rstrip(b'=')
    now = int(time.time())
    header = encode(b'{"alg":"RS256","typ":"JWT"}')
    payload = encode(json.dumps({'iss': client_id, 'sub': user_id,
        'aud': auth_host(environment), 'iat': now, 'exp': now + 3600,
        'scope': 'signature impersonation'}, separators=(',', ':')).encode())
    try:
        key = serialization.load_pem_private_key(private_key.encode(), password=None)
        if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
            raise ValueError()
        message = header + b'.' + payload
        return (message + b'.' + encode(key.sign(message, padding.PKCS1v15(), hashes.SHA256()))).decode()
    except (ValueError, TypeError):
        raise UserError(_('Enter the unencrypted RSA private key registered to this DocuSign integration (at least 2048 bits).')) from None


def request(method, url, **kwargs):
    """Never return provider errors, tokens or document bodies in error text."""
    try:
        with requests.request(method, url, timeout=(5, 45), allow_redirects=False,
                              stream=True, **kwargs) as response:
            if response.status_code >= 300:
                if response.status_code == 400 and url.endswith('/oauth/token'):
                    raise UserError(_('DocuSign authentication failed. Check the integration key, user ID, RSA key and signature/impersonation consent.'))
                raise UserError(_('DocuSign refused the request (HTTP %s). Check API access, consent and account permissions.', response.status_code))
            parts, size = [], 0
            for part in response.iter_content(65536):
                size += len(part)
                if size > 15 * 1024 * 1024:
                    raise UserError(_('The DocuSign response exceeds the 15 MB limit.'))
                parts.append(part)
            response._content = b''.join(parts)
            response._content_consumed = True
            return response
    except requests.RequestException:
        raise UserError(_('DocuSign could not be reached. Check status before retrying a send or cancellation.')) from None


def valid_hmac(secret, raw, signatures):
    if not secret:
        return False
    expected = base64.b64encode(hmac.new(secret.encode(), raw, hashlib.sha256).digest()).decode()
    return any(hmac.compare_digest(expected, signature) for signature in signatures
               if signature and signature.isascii())
