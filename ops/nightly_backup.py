#!/usr/bin/env python3
"""Nightly copy of every active database and its stored files.

One dated folder per database per night:

    <root>/<db>/<YYYY-MM-DD>/db.dump      pg_dump custom format, checked with pg_restore --list
    <root>/<db>/<YYYY-MM-DD>/filestore/   hard links to the live filestore (no extra space:
                                          Odoo never rewrites a stored file, it writes a new one)
    <root>/<db>/<YYYY-MM-DD>/OK           written last; a folder without it is incomplete

Retention is per database (owner ruling 2026-10-23: rize 30 days, the rest 7). The
newest complete copy of a database is never deleted, whatever its age. Copies live on
the same disk as the server, so this protects against mistakes, not against losing it.
"""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

DAY_FORMAT = '%Y-%m-%d'


def log(**fields):
    fields['at'] = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    print(json.dumps(fields), flush=True)


def dated_copies(db_root):
    """(day, path, complete) for every dated folder, newest first. Anything else is ignored."""
    found = []
    if not db_root.is_dir() or db_root.is_symlink():
        return found
    for path in db_root.iterdir():
        if path.is_symlink() or not path.is_dir():
            continue
        try:
            day = datetime.datetime.strptime(path.name, DAY_FORMAT).date()
        except ValueError:
            continue
        found.append((day, path, (path / 'OK').is_file()))
    return sorted(found, reverse=True)


def expired(copies, today, keep_days):
    """Folders to delete: complete copies older than keep_days, never the newest complete
    one; incomplete leftovers once they are a day old (tonight's may still be running)."""
    newest_ok = next((p for _, p, ok in copies if ok), None)
    out = []
    for day, path, ok in copies:
        age = (today - day).days
        if ok and path != newest_ok and age > keep_days:
            out.append(path)
        elif not ok and age >= 1:
            out.append(path)
    return out


def backup_one(db, config, today):
    root = Path(config['backup_root'])
    target = root / db / today.strftime(DAY_FORMAT)
    if (target / 'OK').is_file():
        log(db=db, step='backup', result='already done', path=str(target))
        return True
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, mode=0o700)
    dump = target / 'db.dump'
    with open(dump, 'wb') as stream:
        subprocess.run(['runuser', '-u', 'postgres', '--', 'pg_dump', '-Fc', '-d', db],
                       stdout=stream, check=True, timeout=3600)
    subprocess.run(['pg_restore', '--list', str(dump)], stdout=subprocess.DEVNULL,
                   check=True, timeout=600)
    source = Path(config['filestore_root']) / db
    if source.is_dir():
        # -a keeps owners and times; -l links instead of copying.
        subprocess.run(['cp', '-al', str(source), str(target / 'filestore')],
                       check=True, timeout=3600)
    (target / 'OK').write_text(json.dumps({
        'database': db, 'dump_bytes': dump.stat().st_size,
        'filestore': source.is_dir()}))
    log(db=db, step='backup', result='done', path=str(target), dump_bytes=dump.stat().st_size)
    return True


def prune_one(db, config, today, apply):
    keep = config['keep_days'].get(db, config['keep_days']['default'])
    if not isinstance(keep, int) or isinstance(keep, bool) or keep < 1:
        raise ValueError('keep_days for %s must be a positive number of days' % db)
    removed = []
    for path in expired(dated_copies(Path(config['backup_root']) / db), today, keep):
        if apply:
            shutil.rmtree(path)
        removed.append(str(path))
    log(db=db, step='prune', keep_days=keep, removed=removed, apply=apply)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--config', default='/etc/payobook/nightly-backup.json')
    parser.add_argument('--prune-only', action='store_true')
    parser.add_argument('--dry-run', action='store_true', help='report what pruning would delete')
    args = parser.parse_args(argv)
    config = json.loads(Path(args.config).read_text())
    root = Path(config['backup_root'])
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = open(root / '.lock', 'w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    today = datetime.datetime.now(datetime.timezone.utc).date()
    failed = []
    for db in config['databases']:
        if not args.prune_only and not args.dry_run:
            try:
                backup_one(db, config, today)
            except Exception as e:                       # noqa: BLE001 - one bad db must not stop the rest
                failed.append(db)
                log(db=db, step='backup', result='FAILED', error=str(e)[:500])
                continue                                # never prune a database whose copy failed tonight
        prune_one(db, config, today, apply=not args.dry_run)
    if failed:
        log(step='summary', result='FAILED', failed=failed)
        return 1
    log(step='summary', result='ok')
    return 0


if __name__ == '__main__':
    sys.exit(main())
