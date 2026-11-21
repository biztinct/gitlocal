#!/usr/bin/env python3
"""Conservative server retention. Dry run unless --apply is supplied."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import time
import zipfile


DATA_SUFFIXES = {'.xlsx', '.xls', '.csv', '.tsv', '.pdf', '.json', '.png'}


def stamp(path):
    st = path.lstat()
    return (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_ctime_ns, st.st_size)


def active_paths(proc=Path('/proc')):
    """Protect working directories, open files and absolute command arguments."""
    protected = set()
    for task in proc.iterdir():
        if not task.name.isdigit():
            continue
        try:
            protected.add((task / 'cwd').resolve())
            for fd in (task / 'fd').iterdir():
                try:
                    protected.add(fd.resolve())
                except OSError:
                    pass
            for arg in (task / 'cmdline').read_bytes().split(b'\0'):
                value = arg.decode(errors='replace')
                if value.startswith('/'):
                    protected.add(Path(value).resolve())
        except (OSError, PermissionError):
            continue
    addons = Path('/odoo/odoo-server/addons')
    if addons.is_dir():
        protected.update(p.resolve() for p in addons.iterdir() if p.is_symlink())
    return protected


def is_active(path, protected):
    return any(p == path or path in p.parents or (
        Path('/tmp') in p.parents and p in path.parents) for p in protected)


def old_tree(path, cutoff):
    for parent, dirs, files in os.walk(path, followlinks=False):
        for name in ['.'] + dirs + files:
            p = Path(parent) / name
            if p.is_symlink() or p.lstat().st_mtime >= cutoff or p.lstat().st_ctime >= cutoff:
                return False
    return True


def code_archive(path):
    """Only archives entirely composed of manifested addon directories."""
    try:
        with tarfile.open(path) as archive:
            names = [Path(m.name) for m in archive.getmembers() if m.isfile()]
        roots = {p.parent for p in names if p.name == '__manifest__.py'}
        return bool(roots) and all(not p.is_absolute() and '..' not in p.parts
            and any(p == r or r in p.parents for r in roots) for p in names)
    except (OSError, tarfile.TarError):
        return False


def temp_candidates(root, cutoff, protected):
    for parent, dirs, files in os.walk(root, topdown=True, followlinks=False):
        base = Path(parent)
        dirs[:] = [d for d in dirs if not (base / d).is_symlink()
            and not d.startswith(('.', 'systemd-', 'snap.'))]
        if base != root and (base / '__manifest__.py').is_file():
            dirs[:] = []
            if not is_active(base, protected) and old_tree(base, cutoff):
                yield base, 'inactive addon copy'
            continue
        for name in files:
            path = base / name
            if path.is_symlink() or not path.is_file() or path.suffix in DATA_SUFFIXES:
                continue
            st = path.stat()
            if max(st.st_mtime, st.st_ctime) >= cutoff or is_active(path, protected):
                continue
            if path.suffix == '.log':
                yield path, 'completed temporary log'
            elif name.endswith(('.tar.gz', '.tgz', '.tar')) and code_archive(path):
                yield path, 'inactive addon archive'


def backup_database(path):
    """Inspect the backup itself; a filename is never proof of its database."""
    try:
        if path.suffix == '.zip':
            with zipfile.ZipFile(path) as archive:
                info = archive.getinfo('manifest.json')
                if info.file_size > 1024 * 1024 or 'dump.sql' not in archive.namelist():
                    return None
                manifest = json.loads(archive.read(info))
                database = manifest.get('db_name') if isinstance(manifest, dict) else None
                return database if isinstance(database, str) else None
        if path.suffix in {'.dump', '.backup'}:
            result = subprocess.run(['pg_restore', '--list', str(path)],
                capture_output=True, text=True, timeout=60, check=True)
            match = re.search(r'^;\s+dbname:\s*(\S+)\s*$', result.stdout, re.M)
            return match.group(1) if match else None
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.SubprocessError):
        return None


def backup_candidates(config, cutoff, registered, protected):
    root = Path(config['backup_root']).resolve()
    registered = {str(Path(p).resolve()) for p in registered}
    allowed = set(config['nonproduction_databases']) - set(config['production_databases']) - {'rize', 'abm'}
    permanent = [Path(p).resolve() for p in config['permanent_archives']]
    groups = {}
    for parent, dirs, files in os.walk(root, followlinks=False):
        base = Path(parent)
        dirs[:] = [d for d in dirs if not (base / d).is_symlink()]
        for name in files:
            p = base / name
            if p.is_symlink() or not p.is_file() or any(p == a or a in p.parents for a in permanent):
                continue
            database = backup_database(p)
            if database in allowed:
                groups.setdefault(database, []).append(p)
    for paths in groups.values():
        paths.sort(key=lambda p: (p.stat().st_mtime_ns, str(p)), reverse=True)
        for path in paths[1:]:
            if (str(path) not in registered and max(path.stat().st_mtime, path.stat().st_ctime) < cutoff
                    and not is_active(path, protected)):
                yield path, 'expired nonproduction database backup'


def registered_backups(database):
    result = subprocess.run(['sudo', '-u', 'postgres', 'psql', '-v', 'ON_ERROR_STOP=1',
        '-d', database, '-Atc', 'SELECT path FROM pb_tenant_backup WHERE path IS NOT NULL'],
        capture_output=True, text=True, check=True)
    return set(result.stdout.splitlines())


def prune_registered(database):
    code = "n=env['pb.tenants']._cron_prune_backups();env.cr.commit();print('PRUNED_REGISTERED',n)"
    subprocess.run(['sudo', '-u', 'odoo', '/odoo/odoo-server/odoo-bin', 'shell',
        '-c', '/etc/odoo-server.conf', '-d', database, '--no-http', '--workers=0',
        '--max-cron-threads=0', '--shell-interface=python', '--logfile=/var/log/odoo/odoo-server.log'],
        input=code, text=True, check=True, timeout=1800)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['tmp', 'backups'])
    parser.add_argument('--config', default='/etc/payobook/storage-maintenance.json')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    days = config['retention_days']
    if not isinstance(days, int) or isinstance(days, bool) or days < 1:
        raise ValueError('Retention must be a positive number of days')
    cutoff = time.time() - days * 86400
    with open('/tmp/payobook-studio-deploy.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({'skipped': 'Deployment or maintenance is running'}))
            return
        if args.mode == 'backups':
            if args.apply:
                prune_registered(config['control_database'])
            registered = registered_backups(config['control_database'])
        protected = active_paths()
        candidates = (temp_candidates(Path(config['temporary_root']).resolve(), cutoff, protected)
            if args.mode == 'tmp' else backup_candidates(config, cutoff, registered, protected))
        removed = 0
        for path, reason in candidates:
            original = stamp(path)
            print(json.dumps({'path': str(path), 'reason': reason, 'apply': args.apply}), flush=True)
            if args.apply:
                # Refresh process handles and file identity immediately before deletion.
                if is_active(path, active_paths()) or stamp(path) != original:
                    continue
                if path.is_dir():
                    if not old_tree(path, cutoff):
                        continue
                    shutil.rmtree(path)
                else:
                    path.unlink()
                removed += 1
        print(json.dumps({'mode': args.mode, 'retention_days': days, 'removed': removed, 'apply': args.apply}))


if __name__ == '__main__':
    main()
