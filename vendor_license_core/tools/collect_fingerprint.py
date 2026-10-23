#!/usr/bin/env python3
"""
Collect Server Fingerprint

Run this on the CLIENT SERVER to get the hardware fingerprint hash.
Send the output to your vendor for license generation.

Usage:
    python3 collect_fingerprint.py

No dependencies required — uses only Python standard library.
"""
import hashlib
import uuid
import platform


def collect_fingerprint():
    components = []

    # 1. MAC address
    try:
        mac = hex(uuid.getnode())
        components.append(mac)
    except Exception:
        components.append('no-mac')

    # 2. Machine ID
    machine_id = 'no-machine-id'
    for path in ('/etc/machine-id', '/var/lib/dbus/machine-id'):
        try:
            with open(path, 'r') as f:
                machine_id = f.read().strip()
                break
        except (IOError, OSError):
            continue
    components.append(machine_id)

    # 3. CPU
    try:
        cpu = platform.processor() or platform.machine() or 'unknown-cpu'
        components.append(cpu)
    except Exception:
        components.append('unknown-cpu')

    raw = '|'.join(components)
    fingerprint = hashlib.sha256(raw.encode('utf-8')).hexdigest()

    print("═" * 60)
    print("  SERVER FINGERPRINT")
    print("═" * 60)
    print()
    print(f"  Fingerprint Hash: {fingerprint}")
    print()
    print(f"  Components:")
    print(f"    MAC:        {components[0]}")
    print(f"    Machine ID: {components[1][:20]}...")
    print(f"    CPU:        {components[2]}")
    print()
    print("  Send the Fingerprint Hash to your software vendor")
    print("  for license activation.")
    print()
    print("═" * 60)

    return fingerprint


if __name__ == '__main__':
    collect_fingerprint()
