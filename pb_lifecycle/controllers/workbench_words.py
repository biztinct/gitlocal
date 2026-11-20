# -*- coding: utf-8 -*-
"""The Studio workbench's words in the signed-in person's language (WF2 P6b).

The workbench (`static/workflow/`) is an iframe app of classic scripts with
no framework translation. Its phrases are ordinary `.po` entries of this
module (`#. odoo-javascript`, occurrence `code:addons/pb_lifecycle/static/
workflow/<file>.js:0`). This route serves only those entries, as one small
script that hands them to the workbench's `_t` (static/workflow/i18n.js)
before anything is drawn. English, or any language without entries, gets an
empty dictionary and the workbench keeps its own English words.

The `.po` files are found with the framework's own `get_po_paths` (base
language file first, then the full one, as `code_translations` does) and
read with polib, the parser the framework's `PoFileReader` wraps. polib is
used directly because `PoFileReader` keeps only an entry's first code
occurrence, and a phrase shared with a server message has its workbench
occurrence after the Python one.
"""
import hashlib
import json
import logging
import threading

import polib

from odoo import http
from odoo.http import request
from odoo.tools.translate import JAVASCRIPT_TRANSLATION_COMMENT, get_po_paths

_logger = logging.getLogger(__name__)

MODULE = 'pb_lifecycle'
WORKBENCH = 'addons/pb_lifecycle/static/workflow/'
# {(lang, module version): (body, etag)} — the files only change with a deploy,
# which restarts the server and bumps the version.
_CACHE = {}
_LOCK = threading.Lock()


def workbench_words(lang):
    """{English phrase: translation} for the workbench, in `lang`.

    Only entries marked as JavaScript code translations of this module with
    an occurrence on a workbench file; empty and fuzzy ones are left out, so
    the workbench shows its English for them."""
    words = {}
    if not lang or lang == 'en_US':
        return words
    for path in get_po_paths(MODULE, lang):
        try:
            catalogue = polib.pofile(path)
        except (OSError, ValueError, IOError):
            _logger.exception('Workbench words: could not read %s', path)
            continue
        for entry in catalogue:
            if entry.obsolete or entry.fuzzy or not entry.msgid or not entry.msgstr:
                continue
            if JAVASCRIPT_TRANSLATION_COMMENT not in (entry.comment or ''):
                continue
            if not any(str(place).startswith('code:' + WORKBENCH) for place, _line in entry.occurrences):
                continue
            words[entry.msgid] = entry.msgstr
    return words


def _version(env):
    module = env['ir.module.module'].sudo().search([('name', '=', MODULE)], limit=1)
    return module.latest_version or ''


def payload(lang, version):
    """(script body, ETag) for `lang` at this module version, built once per
    process: `_t.load({...});` with the words, or an empty dictionary."""
    key = (lang, version)
    hit = _CACHE.get(key)
    if hit:
        return hit
    with _LOCK:
        hit = _CACHE.get(key)
        if hit:
            return hit
        try:
            words = workbench_words(lang)
        except Exception:  # never stop the workbench from opening
            _logger.exception('Workbench words for %s could not be built', lang)
            words = {}
        # ensure_ascii keeps the script plain ASCII (no line separators in it).
        body = '_t.load(%s);\n' % json.dumps({'lang': lang, 'words': words}, ensure_ascii=True, sort_keys=True)
        etag = '"%s"' % hashlib.sha1(('%s|%s|%s' % (key[0], key[1], body)).encode()).hexdigest()
        _CACHE[key] = (body, etag)
        return _CACHE[key]


# The address must not end in `.js` (or .css/.png/…): the apex site's web
# server gives every such address 2 days in the browser's cache and overrides
# the `no-cache` below, so a person who changed their language kept the old
# words (WF2 P6e, ledger G103/G104). Without the ending the browser keeps its
# copy but asks each time; the ETag carries the language, the module version
# and the words, so the same language answers 304 and a new one gets its words.
# The old `.js` address stays for index.html copies already in browsers.
ROUTES = ['/pb_lifecycle/workflow/words', '/pb_lifecycle/workflow/words.js']


class WorkbenchWords(http.Controller):

    @http.route(ROUTES, type='http', auth='user', methods=['GET'], readonly=True)
    def workbench_words(self, **kwargs):
        lang = request.env.lang or request.env.user.lang or 'en_US'
        body, etag = payload(lang, _version(request.env))
        headers = [
            ('Content-Type', 'application/javascript; charset=utf-8'),
            ('Cache-Control', 'private, no-cache'),
            ('ETag', etag),
            ('Vary', 'Cookie'),
            ('X-Content-Type-Options', 'nosniff'),
        ]
        if etag in (request.httprequest.headers.get('If-None-Match') or ''):
            return request.make_response('', headers=headers, status=304)
        return request.make_response(body, headers=headers)
