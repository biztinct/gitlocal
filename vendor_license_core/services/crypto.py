# -*- coding: utf-8 -*-
"""
RSA Signature Verification with EMBEDDED Public Key

The public key is baked directly into this source file.
On client deployments, this file is PyArmor-obfuscated,
so the key cannot be easily extracted or replaced.
"""
import base64
import json
import logging

_logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# EMBEDDED RSA-4096 PUBLIC KEY
# This is the ONLY copy on the client machine (no .pem file).
# Generate a new keypair with: tools/generate_keypair.py
# Then paste the public key here before obfuscating.
# ═══════════════════════════════════════════════════════════════
_EMBEDDED_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEA7v2jJz3r62ViKfcAc7NS
o2akz5ExzZ9vLp4DPUbYQY9yJXS5xRUYGTvYlalANz+sYJCzqHgmoZvYzDwWrhps
6gMzB5ANaa153TovCk2j1PkbihRBSovGsieP9RISuamVxUlZ0G1UAkZfHyFMjR0x
NiMOyRKsao6SopRnxAIsMQBbWScxstqUTG+i6BF4+T0gHPh9p1+RvIrn2tUO5Pq7
xA6xVKzYVuSQVdRx9g5YRzb5/EqPwtJTU8Yxt9MwYXzubM3G1rI2Gxtatcemah4X
EwAss7fzdnhUd3IfCE8mCsS4pVJrJh+7s7yB/nfQKFXwwJpXuIiqSc5YXCUamaWh
KLYGwyZs+43mLrKt0YUR1wp407Jq9hU4bwPO4XNGKV00z1lT5q5rXxtPslh9zNP/
kc1mCribZtBxtEM6trgoQooWSo7ko2+7pwSD4gw/7/jzhWPHPLNrpVxFPMQeO1Wm
GK68/Cdt0XmueXOf1EwXYqbqWX5vH8laa5q9mhROOhu8gLUaZjdARXtNa/2D+c0D
N88gYnkJO7OfLkVsS2o0VJUFQaxHAS433sTIcCelw5XFuGtQtiJR9LB+YeVdEx2J
Rb6cEL9YoANkXJj8xiUWfDKWymhoLjBziiPcLTbCSXmbWMMSqEXSZegk4BpXGtpG
v7GN9C3a87T6hjzXD3y0+3cCAwEAAQ==
-----END PUBLIC KEY-----"""


def verify_signature(payload_dict, signature_b64):
    """
    Verify that `payload_dict` was signed with our private key.

    Args:
        payload_dict: dict of license fields (without 'signature')
        signature_b64: base64-encoded RSA signature string

    Returns:
        True if signature is valid, False otherwise.
    """
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
    except ImportError:
        _logger.error(
            "License verification failed: 'cryptography' library not installed. "
            "Install with: pip install cryptography"
        )
        return False

    try:
        # Load the embedded public key
        public_key = serialization.load_pem_public_key(
            _EMBEDDED_PUBLIC_KEY_PEM.encode('utf-8')
        )

        # Reconstruct the canonical payload bytes (sorted keys, no signature)
        clean = {k: v for k, v in payload_dict.items() if k != 'signature'}
        payload_bytes = json.dumps(clean, sort_keys=True).encode('utf-8')

        # Decode the signature
        signature_bytes = base64.b64decode(signature_b64)

        # Verify RSA-PSS signature
        public_key.verify(
            signature_bytes,
            payload_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return True

    except Exception as e:
        _logger.warning("RSA signature verification failed: %s", e)
        return False
