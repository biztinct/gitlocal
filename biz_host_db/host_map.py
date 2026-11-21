# Part of biz_host_db — portable Odoo 19 platform layer. License LGPL-3.
"""Exact hostname -> database map in front of `odoo.http.db_filter`.

Every caller reaches the filter as `http.db_filter` (attribute lookup) or as the
module-global name inside odoo/http.py — session resolution, monodb listing,
web/controllers/utils.py, web/controllers/session.py, auth_oauth. Replacing the
module attribute therefore covers all of them.
"""
import logging
import os
import threading

from odoo import http
from odoo.tools import config

_logger = logging.getLogger(__name__)

DEFAULT_PATH = '/etc/odoo-host-db.map'

_lock = threading.Lock()
_cache = {'mtime': None, 'map': {}}


def _path():
    return config.get('host_db_map') or DEFAULT_PATH


def parse(text):
    """`hostname database` per line; blank lines and `#` comments ignored."""
    out = {}
    for raw in text.splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            _logger.warning("biz_host_db: ignoring malformed line %r", raw)
            continue
        out[parts[0].lower().rstrip('.')] = parts[1]
    return out


def current_map():
    path = _path()
    try:
        mtime = os.stat(path).st_mtime
    except OSError:
        return {}
    if mtime != _cache['mtime']:
        with _lock:
            if mtime != _cache['mtime']:
                try:
                    with open(path, encoding='utf-8') as fh:
                        _cache['map'] = parse(fh.read())
                except OSError as e:
                    _logger.warning("biz_host_db: cannot read %s: %s", path, e)
                    _cache['map'] = {}
                _cache['mtime'] = mtime
                _logger.info("biz_host_db: %d host(s) mapped from %s", len(_cache['map']), path)
    return _cache['map']


def _request_host():
    try:
        return http.request.httprequest.environ.get('HTTP_HOST', '')
    except Exception:  # noqa: BLE001 — no request bound (cron, shell)
        return ''


def mapped_db(host):
    host = (host or '').partition(':')[0].lower().rstrip('.')
    return current_map().get(host) if host else None


def install():
    original = http.db_filter
    if getattr(original, '_biz_host_db', False):
        return

    def db_filter(dbs, host=None):
        name = mapped_db(host if host is not None else _request_host())
        if name:
            return [db for db in dbs if db == name]
        return original(dbs, host)

    db_filter._biz_host_db = True
    db_filter.__doc__ = original.__doc__
    http.db_filter = db_filter
    _logger.info("biz_host_db: hostname map active (%s)", _path())
