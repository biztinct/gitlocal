# -*- coding: utf-8 -*-
"""B2 on a database that already has this module.

THREE JOBS, AND EVERY ONE OF THEM IS SOMETHING AN INSTALL DOES AND AN UPGRADE
DOES NOT. `post_init_hook` fires on INSTALL ONLY and never on `-u` — the Odoo
19 trap the ledger records as AM70 — so a database that got `pb_goals` at
19.0.1.0.0 would otherwise come out of this upgrade with the new tables and
none of the things that make them work:

  1. **The new switches.** Six of them (check-ins on, the day of the month,
     the two minimum-months rules, the year-end email, the review lead time).
     Written only where there is no row at all, so a company that has already
     chosen a value keeps it.
  2. **The goal-change route.** `Seed.lay` refuses with a single INFO line
     when the catalogue row is not there yet (R208) and the upgrade reports
     success regardless — which is exactly how B1's first live install ended
     up silently routeless. The daily job runs this again every morning as a
     third, self-healing leg, and this is the second.
  3. **Applicability on the sheets that already exist.** Every goal sheet made
     before this version has no `covered_from`, no `applies_mid_year` and no
     explanation on it — and the defaults on the new columns say "everybody
     gets everything", which is wrong for exactly the people the rule exists
     for. A GATE THAT HAS NOTHING TO CHECK PASSES (R44): a backfill that is
     skipped here means a November joiner is scored on a year they were barely
     in, with nothing anywhere to say why.

Guarded on `version`: with no version this is the fresh install and the hook
has already done all three. Every job is idempotent and none of them is ever
fatal — an upgrade that refuses because a default route could not be laid is a
worse outcome than a route somebody lays by hand a minute later.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _switches(env)
    _routes(env)
    _applicability(env)


def _switches(env):
    from odoo.addons.pb_goals.models.goals_common import DEFAULTS
    icp = env['ir.config_parameter'].sudo()
    added = []
    for key, value in DEFAULTS.items():
        existing = icp.get_param(key)
        if existing is False or existing is None:
            icp.set_param(key, value)
            added.append(key)
    if added:
        _logger.info('pb_goals: %s switch(es) materialised: %s', len(added),
                     ', '.join(added))


def _routes(env):
    """Both routes, in two guards — one failing must not cost the other."""
    for label, module, name in (
            ('goal-sheet', 'goal_set_approval', 'seed_all'),
            ('goal-change', 'change_approval', 'seed_all_changes')):
        try:
            seed = getattr(__import__(
                'odoo.addons.pb_goals.models.%s' % module,
                fromlist=[name]), name)
            laid = seed(env)
            _logger.info('pb_goals: the %s route was laid for %s '
                         'compan(ies)', label, laid)
        except Exception:               # noqa: BLE001 — never fail an upgrade
            _logger.warning('pb_goals: the %s route could not be seeded',
                            label, exc_info=True)


def _applicability(env):
    """Work out which reviews every EXISTING goal sheet gets.

    ONE SAVEPOINT PER SHEET. A sheet whose goal year has no dates on it
    cannot be worked out and must not cost the other four thousand theirs —
    and a bare try/except would, because Postgres aborts the whole
    transaction on an error and every statement after it fails too (R131).
    """
    sheets = env['pb.goal.set'].sudo().search(
        [('applicability_set', '=', False)], order='id')
    done = 0
    for sheet in sheets:
        try:
            with env.cr.savepoint():
                if sheet._stamp_applicability():
                    done += 1
        except Exception:               # noqa: BLE001 — never fail an upgrade
            _logger.warning('pb_goals: sheet %s could not be worked out',
                            sheet.id, exc_info=True)
    _logger.info('pb_goals: which reviews they get was worked out for %s of '
                 '%s goal sheet(s)', done, len(sheets))
