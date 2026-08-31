# -*- coding: utf-8 -*-
"""Install-time setup that a data file cannot honestly do.

TWO THINGS, and both of them are here rather than in XML for the same reason:
the value has to be generated on the machine it will live on.

1. **The inbound connector.** `hr.integration.connector.company_id` is REQUIRED,
   so this record cannot follow the company-less seed rule (R8) — there is no
   such thing as a company-less connector. It is created once, for the main
   company, and never touched again.

2. **Its api key.** The webhook's whole security model is that key. Shipping one
   in a data file would put the same secret in every database and in the git
   history of a public repository. It is minted here with `secrets`, and the
   owner reads it off the connector form.

`post_init_hook` fires on INSTALL ONLY — never on `-u` (a known Odoo 19 trap).
That is exactly the behaviour wanted: a re-upgrade must not roll the key and
break a webhook somebody has already wired up. The body is written idempotently
anyway, so calling it by hand from a shell is safe.
"""

import logging
import secrets

_logger = logging.getLogger(__name__)

CONNECTOR_NAME = 'Zoho People — inbound'


def post_init_hook(env):
    _ensure_inbound_connector(env)
    _ensure_defaults(env)


def _ensure_defaults(env):
    Param = env['ir.config_parameter'].sudo()
    if Param.get_param('pb_zoho_bridge.auto_create_logins') is False:
        Param.set_param('pb_zoho_bridge.auto_create_logins', '1')


def _ensure_inbound_connector(env):
    Connector = env['hr.integration.connector'].sudo()
    existing = Connector.with_context(active_test=False).search(
        [('connector_type', '=', 'zoho'), ('name', '=', CONNECTOR_NAME)],
        limit=1)
    if existing:
        if not existing.api_key:
            existing.write({'api_key': secrets.token_urlsafe(32)})
        return existing
    company = env['res.company'].sudo().search([], order='id', limit=1)
    connector = Connector.create({
        'name': CONNECTOR_NAME,
        'connector_type': 'zoho',
        'active': True,
        'company_id': company.id,
        'auth_type': 'api_key',
        'api_key': secrets.token_urlsafe(32),
        'description': (
            'The door Zoho People pushes joiners and leavers through. '
            'The API Key on this record is the token the push must carry.'),
    })
    _logger.info('pb_zoho_bridge: inbound connector created (id=%s)',
                 connector.id)
    return connector
