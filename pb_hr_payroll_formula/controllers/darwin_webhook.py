# -*- coding: utf-8 -*-
"""
DarwinHR inbound webhook — lets a Darwinbox tenant *push* employee / salary
changes to Payobook instead of (or in addition to) Payobook polling it.

Endpoint
--------
    POST /api/darwin/webhook
    Content-Type: application/json
    {
        "connector_id": 42,
        "token": "<the connector's API key>",
        "data_type": "employee" | "salary" | "dependent" | ...,
        "records": [ { ... raw Darwinbox record ... }, ... ]
    }

Security
--------
- The connector must exist, be of type ``darwin`` and be active.
- The connector must have an ``api_key`` configured; the pushed ``token`` is
  compared to it with a constant-time check. No key configured ⇒ 401.
- Payload is stored **raw only** (hr.api.data.store); it is never transformed,
  posted, or applied to payslips here — promotion goes through the normal
  mapping / import pipeline a human drives.
"""

import hmac
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class DarwinWebhookController(http.Controller):

    @http.route('/api/darwin/webhook', type='json', auth='public',
                methods=['POST'], csrf=False)
    def darwin_webhook(self, connector_id=None, token=None, data_type='employee',
                       records=None, **_kw):
        # type='json' → the JSON-RPC `params` object is unpacked into these kwargs.
        token = token or ''
        data_type = data_type or 'employee'
        records = records or []

        if not connector_id or not token:
            return {'ok': False, 'error': 'connector_id and token are required'}
        if not isinstance(records, list):
            return {'ok': False, 'error': 'records must be a list'}

        Connector = request.env['hr.integration.connector'].sudo()
        connector = Connector.browse(int(connector_id)).exists()
        # Uniform failure for unknown / wrong-type / inactive / unconfigured —
        # don't leak which connectors exist.
        if (not connector or connector.connector_type != 'darwin'
                or not connector.active or not connector.api_key):
            _logger.info("DarwinHR webhook rejected for connector_id=%s", connector_id)
            return {'ok': False, 'error': 'unauthorized'}
        if not hmac.compare_digest(str(token), str(connector.api_key)):
            _logger.warning("DarwinHR webhook bad token for connector %s", connector.id)
            return {'ok': False, 'error': 'unauthorized'}

        try:
            res = connector.webhook_ingest(data_type, records)
        except Exception as e:
            _logger.exception("DarwinHR webhook ingest failed")
            return {'ok': False, 'error': str(e)}

        return {'ok': True, 'stored': res.get('stored', 0), 'data_type': data_type}
