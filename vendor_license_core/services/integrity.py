# -*- coding: utf-8 -*-
"""
File Integrity Check — detects tampering with module Python files.

Generates and verifies SHA-256 checksums for all protected module files.
The manifest is created during build_release.sh and stored alongside
the license at /opt/vendor_license/checksums.json.
"""
import hashlib
import json
import os
import logging

_logger = logging.getLogger(__name__)

CHECKSUMS_PATH = '/opt/vendor_license/checksums.json'
ADDONS_PATH = '/odoo/odoo-server/addons'

# Modules protected by the license system
PROTECTED_MODULES = [
    'vendor_license_core',
    'pb_hr_workforce',
    'pb_hr_flow',
    'om_hr_payroll',
    'pb_hr_payroll_formula',
    'pb_hr_govt',
    'payroll_analytics_approval',
    'pb_hr_payroll_base',
    'pb_hr_payroll_analytics',
]


def _sha256_file(filepath):
    """Compute SHA-256 hex digest of a single file."""
    h = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except (IOError, OSError) as e:
        _logger.warning("Cannot hash file %s: %s", filepath, e)
        return None


def generate_manifest(addons_path=None):
    """
    Generate a checksums manifest for all protected module files.
    Used during build_release.sh — output is checksums.json.

    Args:
        addons_path: path to the addons directory (defaults to ADDONS_PATH)

    Returns:
        dict — {relative_path: sha256_hash}
    """
    base = addons_path or ADDONS_PATH
    manifest = {}

    for module in PROTECTED_MODULES:
        mod_path = os.path.join(base, module)
        if not os.path.isdir(mod_path):
            continue

        for root, dirs, files in os.walk(mod_path):
            # Skip __pycache__, .git, etc.
            dirs[:] = [d for d in dirs if not d.startswith(('.', '__pycache__'))]
            for fname in files:
                if fname.endswith(('.py', '.pyc', '.pyd', '.so')):
                    abs_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(abs_path, base)
                    file_hash = _sha256_file(abs_path)
                    if file_hash:
                        manifest[rel_path] = file_hash

    return manifest


def save_manifest(manifest, output_path=None):
    """Save the manifest dict to a JSON file."""
    path = output_path or CHECKSUMS_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    _logger.info("Integrity manifest saved: %d files → %s", len(manifest), path)


def verify_integrity(addons_path=None):
    """
    Verify all protected module files against the saved manifest.

    Returns:
        dict:
            ok: bool
            message: str
            modified: list of modified file paths
            missing: list of files in manifest but not on disk
            extra: list of files on disk but not in manifest
    """
    result = {
        'ok': True,
        'message': 'All files are intact.',
        'modified': [],
        'missing': [],
        'extra': [],
    }

    if not os.path.isfile(CHECKSUMS_PATH):
        # No manifest = skip integrity check (development mode)
        result['message'] = 'No integrity manifest found (development mode).'
        _logger.debug("No checksums manifest at %s — skipping integrity check", CHECKSUMS_PATH)
        return result

    try:
        with open(CHECKSUMS_PATH, 'r') as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, IOError, OSError) as e:
        result['ok'] = False
        result['message'] = f'Cannot read integrity manifest: {e}'
        return result

    base = addons_path or ADDONS_PATH

    # Check each file in the manifest
    for rel_path, expected_hash in manifest.items():
        abs_path = os.path.join(base, rel_path)
        if not os.path.isfile(abs_path):
            result['missing'].append(rel_path)
            continue

        actual_hash = _sha256_file(abs_path)
        if actual_hash != expected_hash:
            result['modified'].append(rel_path)

    # Check for extra/new Python files not in manifest
    for module in PROTECTED_MODULES:
        mod_path = os.path.join(base, module)
        if not os.path.isdir(mod_path):
            continue
        for root, dirs, files in os.walk(mod_path):
            dirs[:] = [d for d in dirs if not d.startswith(('.', '__pycache__'))]
            for fname in files:
                if fname.endswith(('.py', '.pyc', '.pyd', '.so')):
                    abs_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(abs_path, base)
                    if rel_path not in manifest:
                        result['extra'].append(rel_path)

    if result['modified'] or result['missing']:
        result['ok'] = False
        parts = []
        if result['modified']:
            parts.append(f"{len(result['modified'])} file(s) modified")
        if result['missing']:
            parts.append(f"{len(result['missing'])} file(s) missing")
        result['message'] = (
            f"Integrity check FAILED: {', '.join(parts)}. "
            "Module files may have been tampered with."
        )
        _logger.error(
            "INTEGRITY FAILURE: modified=%s, missing=%s",
            result['modified'], result['missing']
        )
    else:
        _logger.info("Integrity check passed: %d files verified", len(manifest))

    return result
