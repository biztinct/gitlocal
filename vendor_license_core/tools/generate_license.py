#!/usr/bin/env python3
"""
Generate Signed License File

Signs a license JSON with the vendor's RSA private key.
Client cannot forge this without the private key.

Usage:
    python3 generate_license.py \
        --customer "THACO Corporation" \
        --fingerprint "abc123def456..." \
        --expiry "2027-02-07" \
        --max-employees 500 \
        --private-key keys/private_key.pem \
        --output license.json
"""
import argparse
import base64
import json
import os
import sys
from datetime import datetime


def generate_license(customer, fingerprint, expiry, max_employees,
                     private_key_path, output_path):
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
    except ImportError:
        print("ERROR: Install cryptography first: pip install cryptography")
        sys.exit(1)

    # Validate expiry date
    try:
        datetime.strptime(expiry, '%Y-%m-%d')
    except ValueError:
        print(f"ERROR: Invalid date format '{expiry}'. Use YYYY-MM-DD.")
        sys.exit(1)

    # Build license payload
    license_id = f"LIC-{datetime.now().strftime('%Y')}-{customer[:4].upper()}-{os.urandom(2).hex().upper()}"
    payload = {
        "license_id": license_id,
        "customer": customer,
        "fingerprint_hash": fingerprint,
        "expiry": expiry,
        "max_employees": max_employees,
    }

    # Load private key
    if not os.path.isfile(private_key_path):
        print(f"ERROR: Private key not found at {private_key_path}")
        sys.exit(1)

    with open(private_key_path, 'rb') as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)

    # Sign the payload (canonical JSON, sorted keys)
    payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
    signature = private_key.sign(
        payload_bytes,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )

    # Add signature to payload
    payload['signature'] = base64.b64encode(signature).decode('utf-8')

    # Write output
    with open(output_path, 'w') as f:
        json.dump(payload, f, indent=2)

    print(f"✅ License Generated Successfully")
    print(f"   File:          {output_path}")
    print(f"   License ID:    {license_id}")
    print(f"   Customer:      {customer}")
    print(f"   Fingerprint:   {fingerprint[:16]}...")
    print(f"   Expiry:        {expiry}")
    print(f"   Max Employees: {max_employees}")
    print()
    print(f"Next step: copy {output_path} to client server at:")
    print(f"   /opt/vendor_license/license.json")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate signed vendor license')
    parser.add_argument('--customer', required=True, help='Customer name')
    parser.add_argument('--fingerprint', required=True,
                        help='Client server fingerprint hash')
    parser.add_argument('--expiry', required=True,
                        help='License expiry date (YYYY-MM-DD)')
    parser.add_argument('--max-employees', type=int, required=True,
                        help='Maximum number of active employees')
    parser.add_argument('--private-key', default='keys/private_key.pem',
                        help='Path to RSA private key (default: keys/private_key.pem)')
    parser.add_argument('--output', '-o', default='license.json',
                        help='Output file (default: license.json)')

    args = parser.parse_args()
    generate_license(
        args.customer, args.fingerprint, args.expiry,
        args.max_employees, args.private_key, args.output
    )
