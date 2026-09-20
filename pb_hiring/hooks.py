# -*- coding: utf-8 -*-
"""Install-time setup.

ONE THING, AND IT IS THE TWO DEFAULT APPROVAL ROUTES. `post_init_hook` fires
on INSTALL ONLY — never on `-u`, a known Odoo 19 trap — so the migration
beside it lays the same routes on a database that already has the module. Both
are idempotent, and neither is ever fatal: a module that cannot be installed
because a route could not be laid is a worse outcome than a route somebody
lays a minute later (ledger AM70/AM75).

NOTHING ELSE IS SEEDED. There is deliberately no starter hiring rule and no
starter job board: a rule that names a recruiter is a statement about a real
person, and guessing one is worse than the board saying plainly that nobody
has been named.
"""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    _seed_approval_routes(env)


def _seed_approval_routes(env):
    for module, label in (('requisition_approval', 'hiring request'),
                          ('jd_approval', 'job description'),
                          ('offer_approval', 'offer'),
                          ('cover_approval', 'recruiter cover')):
        try:
            mod = __import__(
                'odoo.addons.pb_hiring.models.%s' % module,
                fromlist=['seed_all'])
            mod.seed_all(env)
        except Exception:               # noqa: BLE001 — never fail an install
            _logger.exception('pb_hiring: the default %s route could not be '
                              'laid', label)
