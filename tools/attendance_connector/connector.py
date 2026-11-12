"""Payobook desktop MDB collector. No writes to source; no terminal connections.

Standard library transport/queue + pinned read-only access-parser. Windows DPAPI
protects credentials and queued source rows for the scheduled task's user.
"""
import argparse
import base64
import contextlib
import ctypes
from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

VERSION = '1.0.0'
COLUMNS = ('UserFullCode', 'UserEnrollNumber', 'TimeDate', 'TimeStr', 'TimeType', 'TimeSource', 'MachineNo', 'CardNo')
BATCH_SIZE = 500


def canonical(row):
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def protect(value, decrypt=False):
    if os.name != 'nt':
        # Mac is for an explicitly local test harness, never a Windows install.
        if os.environ.get('PAYOBOOK_LOCAL_TEST') != '1':
            raise RuntimeError('This package requires Windows. Use the documented local test harness on Mac.')
        return value
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_char))]
    buffer = ctypes.create_string_buffer(value)
    source = Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    target = Blob()
    crypt = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    # UI_FORBIDDEN. CurrentUser scope: task must run as the setup user.
    if not crypt(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        ctypes.windll.kernel32.LocalFree.restype = ctypes.c_void_p
        ctypes.windll.kernel32.LocalFree(target.data)


def save_config(home, config):
    home.mkdir(parents=True, exist_ok=True)
    temp = home / 'settings.tmp'
    temp.write_bytes(protect(canonical(config).encode()))
    if os.name != 'nt':
        temp.chmod(0o600)
    os.replace(temp, home / 'settings.bin')


def load_config(home):
    return json.loads(protect((home / 'settings.bin').read_bytes(), decrypt=True))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the connector bearer token to a different address.
        raise RuntimeError('Unexpected server redirect. Check the Payobook website address.')


def post(base, operation, payload, token=None):
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise ValueError('Enter only the HTTPS Payobook website address, without a path or query.')
    headers = {'Content-Type': 'application/json', 'User-Agent': 'PayobookAttendanceConnector/' + VERSION}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(base.rstrip('/') + '/clock-bridge/v1/' + operation,
        data=canonical(payload).encode(), headers=headers, method='POST')
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=90) as res:
            result = json.loads(res.read(2 * 1024 * 1024))
        if not isinstance(result, dict):
            raise RuntimeError('Invalid server acknowledgement.')
        return result
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError('Payobook access was revoked or pairing expired. Generate a new code and pair again.') from None
        raise RuntimeError('Payobook returned HTTP %s; queued records will retry.' % exc.code) from None


def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as src:
        for block in iter(lambda: src.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


@contextlib.contextmanager
def stable_copy(path, home):
    """Never hold a database lock or parse a known-changing file."""
    path = Path(path)
    before = path.stat()
    if before.st_size > 2 * 1024**3:
        raise RuntimeError('MDB exceeds the supported 2 GB file size.')
    with tempfile.TemporaryDirectory(prefix='read-', dir=home) as temp:
        copy = Path(temp) / 'source.mdb'
        shutil.copyfile(path, copy)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or file_hash(copy) != file_hash(path):
            raise RuntimeError('Mitaco is updating the database. The next scheduled scan will retry.')
        yield copy
        # Parsing uses only the stable copy. Late source writes are read next scan.


def extract(path, home, history_from):
    from access_parser import AccessParser
    with stable_copy(path, home) as snapshot:
        db = AccessParser(str(snapshot))
        if 'CheckInOut' not in db.catalog:
            raise RuntimeError('Expected the Mitaco CheckInOut table. No source tables were changed.')
        table = db.parse_table('CheckInOut')
        if not all(k in table for k in COLUMNS) or len({len(table[k]) for k in COLUMNS}) != 1:
            raise RuntimeError('Unsupported or damaged Mitaco table layout. Ask IT to check the MDB.')
        total = len(table['TimeStr'])
        rows, latest = [], ''
        for index in range(total):
            row = {k: '' if table[k][index] is None else str(table[k][index]) for k in COLUMNS}
            # Numbers are not human-readable master data; preserve codes as read.
            stamp = row['TimeStr']
            try:
                parsed = datetime.strptime(stamp, '%Y-%m-%d %H:%M:%S')
                latest = max(latest, stamp)
                if parsed.strftime('%Y-%m-%d') < history_from:
                    continue
            except (ValueError, TypeError):
                pass  # invalid source timestamps go to Payobook review too
            rows.append(row)
        return rows, {'source_rows': total, 'latest_punch': latest, 'read_ok': True}


class Queue:
    def __init__(self, home):
        self.db = sqlite3.connect(home / 'queue.sqlite', timeout=10)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS events (hash TEXT PRIMARY KEY, payload BLOB, acknowledged INTEGER NOT NULL DEFAULT 0)')
        self.db.commit()

    def add(self, rows):
        with self.db:
            for row in rows:
                raw = canonical(row).encode()
                key = hashlib.sha256(raw).hexdigest()
                if not self.db.execute('SELECT 1 FROM events WHERE hash=?', [key]).fetchone():
                    self.db.execute('INSERT INTO events(hash,payload) VALUES(?,?)', [key, protect(raw)])

    def batch(self):
        return [(key, json.loads(protect(raw, decrypt=True))) for key, raw in
            self.db.execute('SELECT hash,payload FROM events WHERE acknowledged=0 ORDER BY rowid LIMIT ?', [BATCH_SIZE])]

    def acknowledge(self, keys):
        with self.db:
            self.db.executemany('UPDATE events SET acknowledged=1,payload=NULL WHERE hash=?', [(k,) for k in keys])

    def count(self):
        return self.db.execute('SELECT count(*) FROM events WHERE acknowledged=0').fetchone()[0]

    def replay(self):
        # Delete ack fingerprints only. Pending rows are never discarded.
        with self.db:
            self.db.execute('DELETE FROM events WHERE acknowledged=1')

    def close(self):
        self.db.close()


def queue_home(home, config):
    binding = hashlib.sha256((config['server'].rstrip('/') + '|' + str(config['remote'].get('connector_id', 'test'))).encode()).hexdigest()
    folder = home / 'sources' / binding
    folder.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt':
        folder.chmod(0o700)
    return folder


def sync(home, config, sender=post):
    q = Queue(queue_home(home, config))
    status = {'version': VERSION, 'read_ok': False, 'error': ''}
    try:
        try:
            rows, info = extract(config['database'], home, config['remote']['history_from'])
            q.add(rows)
            status.update(info)
        except Exception as exc:
            # Source unreadability does not block upload of already queued rows.
            status['error'] = '%s: %s' % (type(exc).__name__, str(exc)[:400])
        sent = 0
        while True:
            batch = q.batch()
            status['pending'] = q.count()
            result = sender(config['server'], 'sync', {'rows': [r for _, r in batch], 'status': status}, config['token'])
            if result.get('acknowledged') != len(batch):
                raise RuntimeError('Incomplete acknowledgement. Records remain queued for retry.')
            q.acknowledge([key for key, _ in batch])
            config['remote'] = result.get('config', config['remote'])
            save_config(home, config)
            sent += len(batch)
            if not batch:
                break
        return {'sent': sent, 'pending': q.count(), **status}
    finally:
        q.close()


@contextlib.contextmanager
def instance_lock(home):
    f = open(home / 'worker.lock', 'a+b')
    try:
        f.seek(0); f.write(b'1'); f.flush(); f.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        f.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['pair', 'check', 'sync', 'replay'])
    parser.add_argument('--home', default=str(Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'PayobookAttendance' / 'data'))
    parser.add_argument('--database')
    args = parser.parse_args()
    home = Path(args.home); home.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt':
        home.chmod(0o700)
    logging.basicConfig(level=logging.ERROR)
    try:
        with instance_lock(home):
            if args.command == 'pair':
                details = json.load(sys.stdin)  # never put secrets in command arguments
                old = load_config(home) if (home / 'settings.bin').exists() else {}
                installation = old.get('installation_id', str(uuid.uuid4()))
                result = post(details['server'], 'pair', {'code': details['code'], 'installation_id': installation})
                config = {'server': details['server'], 'database': details['database'], 'installation_id': installation,
                          'token': result['token'], 'remote': result['config']}
                save_config(home, config)
                q = Queue(queue_home(home, config)); q.replay(); q.close()
                output = {'paired': True, 'name': result['config']['name']}
            elif args.command == 'check':
                rows, info = extract(args.database, home, '1900-01-01')
                output = {**info, 'unique_records': len({canonical(r) for r in rows}), 'read_only': True}
            elif args.command == 'replay':
                config = load_config(home)
                q = Queue(queue_home(home, config)); q.replay(); q.close()
                output = {'rescan': True}
            else:
                config = load_config(home)
                # Scheduled task wakes every five minutes; server controls interval.
                marker = home / 'last_attempt'
                wait = max(5, int(config['remote'].get('interval_minutes', 15))) * 60
                if marker.exists() and time.time() - marker.stat().st_mtime < wait:
                    output = {'waiting_for_next_scan': True}
                else:
                    marker.touch()
                    output = sync(home, config)
            (home / 'status.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
            print(json.dumps(output))
    except Exception as exc:
        # No token, row content, or employee details in diagnostics.
        output = {'error': str(exc)[:500], 'time': time.strftime('%Y-%m-%d %H:%M:%S')}
        (home / 'status.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
        print(json.dumps(output))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
