# -*- coding: utf-8 -*-
"""
Hardware Fingerprint Generator
Produces a unique SHA-256 hash from: MAC address + /etc/machine-id + CPU info
"""
import hashlib
import uuid
import platform
import logging

_logger = logging.getLogger(__name__)

# Cache the fingerprint (doesn't change during runtime)
_cached_fingerprint = None


def get_fingerprint():
    """Return a SHA-256 hex digest identifying this machine."""
    global _cached_fingerprint
    if _cached_fingerprint:
        return _cached_fingerprint

    components = []

    # 1. MAC address (primary network interface)
    try:
        mac = hex(uuid.getnode())
        components.append(mac)
    except Exception:
        components.append('no-mac')

    # 2. Machine ID (Linux: /etc/machine-id, systemd-based)
    machine_id = 'no-machine-id'
    for path in ('/etc/machine-id', '/var/lib/dbus/machine-id'):
        try:
            with open(path, 'r') as f:
                machine_id = f.read().strip()
                break
        except (IOError, OSError):
            continue
    components.append(machine_id)

    # 3. CPU identifier
    try:
        cpu = platform.processor() or platform.machine() or 'unknown-cpu'
        components.append(cpu)
    except Exception:
        components.append('unknown-cpu')

    raw = '|'.join(components)
    _cached_fingerprint = hashlib.sha256(raw.encode('utf-8')).hexdigest()

    _logger.info(
        "Hardware fingerprint computed: %s...%s",
        _cached_fingerprint[:8], _cached_fingerprint[-8:]
    )
    return _cached_fingerprint
