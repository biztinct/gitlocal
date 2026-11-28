#!/usr/bin/env python3
"""Weekly prune of pre-deploy backups in /odoo/backups. Dry run unless --apply is supplied.

Owner ruling 2026-11-25: update (deploy) backups older than 3 days are deleted for every database,
rize and sudima included. The nightly backups in /odoo/nightly-backups (own retention) and the
permanent archives in /odoo/archives are never touched by this script.

A top-level entry of the backup root is removed only when:
- it is not a symlink and nothing inside it is a symlink,
- nothing inside it was modified or changed within the retention window,
- it is not among the newest KEEP_NEWEST entries (always kept, whatever their age),
- no running process has it open, as its working directory, or as a command argument,
- the shared deploy lock is free (a deploy or other maintenance skips this run).
"""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import time

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('storage_maintenance', HERE / 'storage_maintenance.py')
sm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sm)

LOCK = '/tmp/payobook-studio-deploy.lock'
KEEP_NEWEST = 5
NEVER = (Path('/odoo/archives'), Path('/odoo/nightly-backups'))


def newest_change(path):
    """Newest mtime/ctime of the entry and everything below it (a symlink inside = never old)."""
    newest = 0.0
    for parent, dirs, files in os.walk(path, followlinks=False):
        for name in ['.'] + dirs + files:
            p = Path(parent) / name
            if p.is_symlink():
                return float('inf')
            st = p.lstat()
            newest = max(newest, st.st_mtime, st.st_ctime)
    return newest


def candidates(root, cutoff, protected, keep=KEEP_NEWEST):
    root = Path(root).resolve()
    if any(root == n or n in root.parents or root in n.parents for n in NEVER):
        raise ValueError('refusing to prune a protected archive root: %s' % root)
    entries = []
    for entry in root.iterdir():
        if entry.is_symlink():
            continue
        entries.append((newest_change(entry), entry))
    entries.sort(key=lambda t: (t[0], str(t[1])), reverse=True)
    for newest, entry in entries[keep:]:
        if newest < cutoff and not sm.is_active(entry.resolve(), protected):
            yield entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='/odoo/backups')
    parser.add_argument('--days', type=int, default=3)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.days < 1:
        raise ValueError('Retention must be a positive number of days')
    cutoff = time.time() - args.days * 86400
    with open(LOCK, 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({'mode': 'deploy-backups', 'skipped': 'Deployment or maintenance is running'}))
            return
        removed, freed = [], 0
        for entry in list(candidates(args.root, cutoff, sm.active_paths())):
            size = sum(f.stat().st_size for f in entry.rglob('*') if f.is_file()) if entry.is_dir() else entry.stat().st_size
            print(json.dumps({'path': str(entry), 'reason': 'deploy backup older than %d days' % args.days,
                'apply': args.apply}), flush=True)
            if not args.apply:
                continue
            # Re-check immediately before deleting: still old, still not in use.
            if newest_change(entry) >= cutoff or sm.is_active(entry.resolve(), sm.active_paths()):
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
            removed.append(entry.name)
            freed += size
        print(json.dumps({'mode': 'deploy-backups', 'retention_days': args.days, 'removed': len(removed),
            'freed_mb': freed // 1048576, 'apply': args.apply}))


if __name__ == '__main__':
    main()
