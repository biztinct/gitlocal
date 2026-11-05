# -*- coding: utf-8 -*-
"""The door attendance machines push through (ZK PUSH / ADMS, "iclock").

    GET  /iclock/cdata?SN=…&options=all&pushver=…   handshake
    POST /iclock/cdata?SN=…&table=ATTLOG&Stamp=…    punches
    GET  /iclock/getrequest?SN=…[&INFO=…]           poll for commands
    POST /iclock/devicecmd?SN=…                     command results
    …/ping, /push, /registry, /querydata, /rtdata   PUSH 3.x and odd builds
    any other /iclock/* path                        200 OK

A thin door: it reads the request and hands it to `pb.clock.adms.handle`,
which decides everything (tenancy, serial, plain connection, ledger writes).

WHY THE ROUTE FLAGS
  * auth='none' — a machine has no login; the serial is its identity and the
    allow-list (`pb.clock.device.state`) is the lock.
  * readonly=False — an auth='none' route defaults to the READ-ONLY cursor on
    this build (http.py: `default_mode = auth == 'none'`); every punch would
    otherwise be refused, retried, and logged as a warning.
  * save_session=False — a machine polling every 10 s must not create a
    session file per request.
  * The host picks the database (dbfilter ^%d$): sudima.payobook.com/iclock/…
    lands in `sudima` with no db parameter.

THE BODY. A machine that labels its upload as a web form gets its body parsed
into form fields before this code runs (the dispatcher reads the form), so the
raw text is rebuilt from the fields — lossless for punch lines, which carry no
`&` or `=`.
"""

import logging

from odoo import SUPERUSER_ID, http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

MAX_BODY = 2 * 1024 * 1024


def _text(status, body):
    return Response(body, status=status, content_type='text/plain; charset=utf-8')


def _raw_body(httprequest):
    data = httprequest.get_data(cache=True) or b''
    if not data and httprequest.form:
        parts = []
        for key, value in httprequest.form.items(multi=True):
            parts.append(key if value == '' else '%s=%s' % (key, value))
        return '&'.join(parts)
    return data.decode('utf-8', errors='replace')


def _meta(httprequest):
    headers = httprequest.headers
    fwd = (headers.get('X-Forwarded-For') or '').split(',')[0].strip()
    proto = (headers.get('X-Forwarded-Proto') or 'https').strip().lower()
    return {
        'ip': (fwd or httprequest.remote_addr or '')[:45],
        'proto': 'http' if proto == 'http' else 'https',
    }


class IclockController(http.Controller):

    @http.route(['/iclock', '/iclock/<path:sub>'], type='http', auth='none',
                methods=['GET', 'POST'], csrf=False, readonly=False,
                save_session=False)
    def iclock(self, sub='', **_kw):
        hr = request.httprequest
        meta = _meta(hr)
        too_big = (hr.content_length or 0) > MAX_BODY
        body = '' if too_big or hr.method == 'GET' else _raw_body(hr)
        meta['too_big'] = too_big
        params = hr.args.to_dict()
        env = request.env(user=SUPERUSER_ID, su=True)
        if 'pb.clock.adms' not in env:
            return _text(200, 'OK')
        try:
            with env.cr.savepoint():
                status, text = env['pb.clock.adms'].handle(
                    sub, hr.method, params, body, meta)
        except Exception:  # noqa: BLE001 — the machine retries; never a trace page
            _logger.exception("pb_clock: the receiver failed for %s %s",
                              hr.method, hr.full_path[:200])
            return _text(500, 'error')
        return _text(status, text)
