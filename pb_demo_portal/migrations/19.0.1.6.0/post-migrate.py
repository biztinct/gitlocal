"""Demo users land on Home, not the bare Dashboard (owner, 2026-10-12).

Sign-up used to give every demo user `action_id = pb_dashboard.action_pb_dashboard`.
Move the demo-group users still on that (or on nothing) to the Home hub, which
opens on Pulse. Anyone pointed somewhere else on purpose is left alone.
Rollback: set `action_id` back to the Dashboard action for the logged ids.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    group = env.ref('pb_demo.group_payobook_demo', raise_if_not_found=False)
    home = env.ref('pb_home_hub.action_pb_home_hub', raise_if_not_found=False)
    if not group or not home:
        return
    dash = env.ref('pb_dashboard.action_pb_dashboard', raise_if_not_found=False)
    cr.execute("""
        UPDATE res_users u SET action_id = %s
          FROM res_groups_users_rel r
         WHERE r.uid = u.id AND r.gid = %s
           AND (u.action_id IS NULL OR u.action_id = %s)
     RETURNING u.id
    """, (home.id, group.id, dash.id if dash else -1))
    ids = sorted(row[0] for row in cr.fetchall())
    _logger.info('pb_demo_portal: %s demo users now land on Home: %s', len(ids), ids)
