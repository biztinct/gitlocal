# -*- coding: utf-8 -*-
"""E3 on a database that already has this module.

`post_init_hook` fires on INSTALL ONLY and never on `-u` — the Odoo 19 trap the
ledger records (AM70) — and every live database already has `pb_training`. So
the three things an install would have done have to be done here as well:

  1. **The switches E3 added.** Nothing BEHAVES wrong without them: every
     reader goes through `flag()`/`number()`/`text()`, which fall back to the
     same defaults in code. But a switch nobody can find on the Settings screen
     is a switch nobody can turn, and one of these decides whether a
     spreadsheet of the company's training figures is emailed out every month.
  2. **The approval route for a training claim.** Without it the claim has no
     published route, the shim stays dormant and the record falls back to its
     own small ladder — which works, but is not the Matrix, and the HR lead
     would never see it in their inbox.
  3. **Nothing else.** In particular no data is back-filled and no existing row
     is touched: there were no claims and no allowances before this upgrade, by
     construction, because the tables did not exist.

Both jobs are idempotent: the switches are written only where there is no row
at all, and `Seed.lay` asks the database what is already there before it
creates anything. Neither is ever fatal — an upgrade that refuses because a
default route could not be laid is a worse outcome than a route somebody lays
by hand a minute later.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _switches(env)
    _route(env)
    _seat_rules(env)


def _seat_rules(env):
    """A SEAT IS A READ **AND A WRITE** — and `noupdate="1"` cannot say so.

    The seat rules ship inside a `noupdate="1"` block, which is right (a
    business that has tuned a record rule must keep its version) and means an
    upgrade never corrects one. E2 shipped the delay's seat rule read-only and
    E3 shipped the claim's the same way, on the reasoning that being asked to
    decide something is not permission to change it — and live, the HR lead
    pressed Agree, the route recorded the approval and the claim did not move,
    because the engine writes the record's own status AS THE PERSON WHO
    DECIDED. The only trace was inside the request's `block_reason`.

    So the correction is made here, by xmlid, and only where the rule is still
    exactly as it shipped — a business that has already widened or narrowed it
    keeps what it chose.
    """
    for xmlid in ('pb_training.rule_claim_seat',
                  'pb_training.rule_delay_seat'):
        rule = env.ref(xmlid, raise_if_not_found=False)
        if not rule:
            continue
        if rule.perm_write:
            continue
        rule.sudo().write({'perm_write': True})
        _logger.info('pb_training: %s now lets the people a route asked to '
                     'decide a request record their decision', xmlid)


def _switches(env):
    from odoo.addons.pb_training.models.training_common import DEFAULTS
    icp = env['ir.config_parameter'].sudo()
    added = []
    for key, value in DEFAULTS.items():
        if not icp.get_param(key):
            icp.set_param(key, value)
            added.append(key)
    _logger.info('pb_training: %s switch(es) materialised: %s',
                 len(added), ', '.join(added) or 'none')


def _route(env):
    try:
        from odoo.addons.pb_training.models.claim_approval import seed_all
        laid = seed_all(env)
        _logger.info('pb_training: the training-claim route was laid for %s '
                     'compan(ies)', laid)
    except Exception:       # noqa: BLE001 — an upgrade must not die on a seed
        _logger.exception('pb_training: the default claim route could not be '
                          'seeded')
