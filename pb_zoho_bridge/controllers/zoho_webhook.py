# -*- coding: utf-8 -*-
"""Zoho People inbound webhook — the door a live tenant pushes through.

Endpoint
--------
    POST /api/zoho/webhook
    Content-Type: application/json
    {
        "connector_id": 42,
        "token": "<the connector's API key>",
        "data_type": "employee",
        "records": [ { ...one raw Zoho People employee record... }, ... ]
    }

Security
--------
Cloned, deliberately line for line, from the DarwinHR webhook
(`pb_hr_payroll_formula/controllers/darwin_webhook.py`) — a second door into the
same building should not have a second lock design.

- The connector must exist, be of type ``zoho``, be active, and have an
  ``api_key`` configured.
- The pushed ``token`` is compared with a constant-time check.
- EVERY failure answers the same word, "unauthorized". A caller who guesses a
  connector id must not be able to tell a wrong id from a wrong token from an
  inactive connector, or the endpoint becomes a way to enumerate what exists.

Unlike the Darwin door this one does more than store: employee records are
carried on into the arrival pipeline, which is where the rules decide whether a
journey opens. The raw payload is still stored first and never edited, so the
audit trail exists whatever the pipeline concludes.
"""

import hmac
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class ZohoWebhookController(http.Controller):

    # `type='jsonrpc'`, not the `type='json'` the Darwin door still uses. They
    # are the same route — 'json' is an alias — but on Odoo 19 the alias emits a
    # DeprecationWarning with a full stack trace into the log on EVERY module
    # load. A new door should not add noise to the log that the next person
    # debugging a real failure has to read past.
    @http.route('/api/zoho/webhook', type='jsonrpc', auth='public',
                methods=['POST'], csrf=False)
    def zoho_webhook(self, connector_id=None, token=None, data_type='employee',
                     records=None, **_kw):
        # The JSON-RPC `params` object is unpacked into these kwargs.
        token = token or ''
        data_type = data_type or 'employee'
        records = records or []

        if not connector_id or not token:
            return {'ok': False, 'error': 'connector_id and token are required'}
        if not isinstance(records, list):
            return {'ok': False, 'error': 'records must be a list'}

        Connector = request.env['hr.integration.connector'].sudo()
        try:
            connector = Connector.browse(int(connector_id)).exists()
        except (TypeError, ValueError):
            connector = Connector.browse()
        # Uniform failure for unknown / wrong-type / inactive / unconfigured.
        if (not connector or connector.connector_type != 'zoho'
                or not connector.active or not connector.api_key):
            _logger.info('Zoho webhook rejected for connector_id=%s',
                         connector_id)
            return {'ok': False, 'error': 'unauthorized'}
        if not hmac.compare_digest(str(token), str(connector.api_key)):
            _logger.warning('Zoho webhook bad token for connector %s',
                            connector.id)
            return {'ok': False, 'error': 'unauthorized'}

        try:
            res = connector.webhook_ingest(data_type, records)
        except Exception as e:
            _logger.exception('Zoho webhook ingest failed')
            return {'ok': False, 'error': str(e)}

        return {'ok': True, 'stored': res.get('stored', 0),
                'data_type': data_type, 'applied': res.get('applied', {})}
