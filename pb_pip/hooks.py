# -*- coding: utf-8 -*-
"""Install-time setup.

TWO THINGS, and neither of them touches an employee record.

  1. **The two seeded templates are pointed at no company.** Seed data's
     `company_id` defaults to the loading user's company (R8), so a template
     installed by whoever ran the upgrade would then be hidden from every other
     company by the standard rule. The data file already ships
     `eval="False"`; this is the belt to that braces, because a template that
     is invisible is a template an HR lead re-creates by hand.
  2. **Nothing else.** In particular there is NO backfill and NO group is
     granted to anybody. P5 backfilled a state onto 4,537 employees because a
     trial state is a fact about everybody; an improvement plan is a fact about
     almost nobody, and inventing one would be worse than useless.

     The GROUPS are deliberately not granted here either. `post_init_hook` runs
     as the installing user, and quietly adding whoever ran an upgrade to the
     group that can read everybody's improvement plan is precisely the failure
     this phase is written to prevent. The data file puts the two built-in
     administrator accounts in `group_pip_head` and nobody else; every other
     person is added by name, by a human, on purpose.

`post_init_hook` fires on INSTALL ONLY — never on `-u` (a known Odoo 19 trap) —
so anything that must survive an upgrade does not belong here.
"""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    _unpin_seed_templates(env)
    _report_groups(env)


def _unpin_seed_templates(env):
    """Any seeded template that picked up a company loses it."""
    try:
        for xmlid in ('pb_pip.pip_template_delivery',
                      'pb_pip.pip_template_collaboration'):
            template = env.ref(xmlid, raise_if_not_found=False)
            if template and template.company_id:
                template.sudo().company_id = False
                _logger.info('pb_pip: %s was pinned to a company — freed',
                             xmlid)
    except Exception:                   # noqa: BLE001 — never fail an install
        _logger.exception('pb_pip: could not free the seeded templates')
    return True


def _report_groups(env):
    """Say in the log who can see this, so nobody has to go looking."""
    try:
        for xmlid in ('pb_pip.group_pip_user', 'pb_pip.group_pip_head'):
            group = env.ref(xmlid, raise_if_not_found=False)
            if not group:
                continue
            names = ', '.join(u.login for u in group.sudo().all_user_ids) \
                or '(nobody)'
            _logger.info('pb_pip: %s -> %s', xmlid, names)
    except Exception:                   # noqa: BLE001
        _logger.exception('pb_pip: could not list the groups')
    return True
