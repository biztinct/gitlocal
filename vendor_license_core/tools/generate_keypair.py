#!/usr/bin/env python3
"""
Generate RSA-4096 Keypair for Vendor License System

Run this ONCE to create your keypair. Keep private_key.pem SECRET.
Paste the public key into services/crypto.py before obfuscating.

Usage:
    python3 generate_keypair.py [output_dir]
    python3 generate_keypair.py              # → saves to ./keys/
    python3 generate_keypair.py ~/vendor_keys # → saves to ~/vendor_keys/
"""
import os
import sys

def generate_keypair(output_dir='keys'):
    try:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        print("ERROR: Install cryptography first: pip install cryptography")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
    )

    # Save private key
    priv_path = os.path.join(output_dir, 'private_key.pem')
    with open(priv_path, 'wb') as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    os.chmod(priv_path, 0o600)

    # Save public key
    pub_path = os.path.join(output_dir, 'public_key.pem')
    public_key = private_key.public_key()
    with open(pub_path, 'wb') as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ))

    print(f"✅ RSA-4096 Keypair Generated")
    print(f"   Private key: {priv_path}  (KEEP SECRET — never deploy!)")
    print(f"   Public key:  {pub_path}")
    print()
    print("Next step: paste the public key into services/crypto.py")
    print("           before running PyArmor obfuscation.")


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else 'keys'
    generate_keypair(out)
