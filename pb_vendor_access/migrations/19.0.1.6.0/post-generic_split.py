# -*- coding: utf-8 -*-
"""After the split: check that nothing was left behind (ACCESS P6).

THE MOVE ITSELF HAPPENS EARLIER AND ELSEWHERE. `biz_access` re-homes every
record that changed owner in its own `pre_init_hook`, which fires before its
models are reflected and before a single data file is read — the only moment at
which it can, because a migration script only ever runs on an UPGRADE and the
generic module is being INSTALLED. By the time this runs, the move is done and
both modules have loaded their data on top of it.

SO THIS SCRIPT ONLY CHECKS AND RE-SEEDS.

  * It counts what is left pointing at this module that should not be, and says
    so loudly rather than quietly: an orphaned external id is a record that the
    NEXT upgrade would decide is stale.
  * It re-runs the catalogue and the left-menu gates. R84/ledger A2 —
    `post_init_hook` fires on INSTALL only, so a catalogue that changed has to
    be asked for. Both passes are create-only and additive: an upgrade never
    widens a role somebody already holds and never takes a role off an entry
    somebody has since edited on the Screens lens.

It changes nobody's permissions.
"""

import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)

#: Everything the generic module took over. If one of these still says it
#: belongs here, the re-homing did not run and the next upgrade would delete it.
SHOULD_HAVE_MOVED = (
    'group_access_manager',
    'rule_delegation_company', 'rule_profile_visible',
    'rule_profile_access_team_all', 'rule_delegation_mine',
    'rule_delegation_access_team_all',
    'access_pb_role_ability_user', 'access_pb_role_ability_access_manager',
    'access_pb_role_profile_user', 'access_pb_role_profile_access_manager',
    'access_pb_access_delegation_user',
    'access_pb_access_delegation_access_manager',
    'cron_access_auto_revert',
    'mail_template_delegation_handed', 'mail_template_delegation_ended',
    'view_pb_role_profile_list', 'view_pb_role_profile_search',
    'view_pb_role_profile_form', 'view_pb_role_ability_list',
    'view_pb_role_ability_form', 'view_pb_access_delegation_list',
    'view_pb_access_delegation_form', 'view_pb_access_delegation_search',
    'view_pb_sidebar_item_list_roles', 'view_pb_sidebar_item_form_roles',
    'action_pb_role_profile', 'action_pb_access_delegation',
    'action_pb_access_board',
)


def migrate(cr, version):
    if not version or not table_exists(cr, 'pb_role_profile'):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})

    # ------------------------------------------------------ the move happened
    cr.execute("""
        SELECT name FROM ir_model_data
         WHERE module = 'pb_vendor_access' AND name IN %s
    """, (SHOULD_HAVE_MOVED,))
    stragglers = [row[0] for row in cr.fetchall()]
    if stragglers:
        _logger.error(
            'pb_vendor_access: %s external id(s) that belong to biz_access '
            'still say they belong here — %s. The next upgrade would treat '
            'them as removed data.', len(stragglers), ', '.join(stragglers))
    else:
        _logger.info(
            'pb_vendor_access: every record the Access home took over is '
            'registered to biz_access')

    cr.execute("""
        SELECT COUNT(*) FROM ir_model_data d
         WHERE d.module IN ('pb_vendor_access', 'biz_access')
           AND d.model NOT LIKE 'ir.model%%'
           AND NOT EXISTS (SELECT 1 FROM ir_model m WHERE m.model = d.model)
    """)
    _logger.info('pb_vendor_access: %s external id(s) point at a model that no '
                 'longer exists', cr.fetchone()[0])

    # ------------------------------------------------------------ the catalogue
    from odoo.addons.pb_vendor_access.hooks import (ensure_catalogue,
                                                    ensure_screen_gates)
    result = ensure_catalogue(env)
    gates = ensure_screen_gates(env)

    cr.execute("SELECT COUNT(*) FROM pb_role_profile WHERE active")
    roles = cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM pb_role_ability WHERE active")
    abilities = cr.fetchone()[0]
    cr.execute("""
        SELECT COUNT(*) FROM res_groups_users_rel r
          JOIN ir_model_data d ON d.res_id = r.gid
         WHERE d.module = 'biz_access' AND d.name = 'group_access_manager'
    """)
    access_team = cr.fetchone()[0]
    _logger.info(
        'pb_vendor_access: after the split — %s roles, %s abilities, %s people '
        'on the access team, %s catalogue rows created, %s left-menu entries '
        'gated', roles, abilities, access_team, result.get('created'),
        gates.get('gated'))
