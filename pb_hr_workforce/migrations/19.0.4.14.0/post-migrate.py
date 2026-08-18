# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P7 — bury the Gen-0 cockpits (WP-3).

Removing a record from a data file DOES NOT delete it (W13.1). Odoo's loader
only ever creates and updates; a `<record>` that disappears from the XML leaves
the row and its `ir_model_data` behind forever, and everything that reads the
table keeps finding it. So the five deletions this version made in the data
files are finished HERE, against the database, and the phase's tests assert the
result from the database rather than from the source.

WHAT WAS DELETED, AND WHY IT HAS TO BE DELETED RATHER THAN RETIRED
------------------------------------------------------------------
Four Gen-0 client cockpits — the Workforce Dashboard, Live Attendance,
Timecards and the Overtime Rules board — plus the legacy Shift Roster grid.
Every one of them was replaced surface by surface during the Workforce redesign
(Today, the Time hub, Schedule, the Overtime Desk), and each was left
"registered but retired" on the rail under W18's retire-never-delete rule.

P7 retires that rule for these five, because it only holds while re-enabling
the item would still WORK. Their JS and CSS are gone from the bundle, so:

  * an `ir.actions.client` whose `tag` is no longer in the browser's action
    registry is a door that can only ever produce an error (W29);
  * an `ir.ui.menu` pointing at a deleted action is worse than a dead link — it
    is a module that will not INSTALL, because Odoo resolves `action=` at load
    time;
  * a retired `pb.sidebar.item` whose `action_xmlid` no longer resolves is not
    a reversible decision, and `pb_today/tests/test_sweep.py` asserts that every
    retired item's action still resolves.

WHY THE SIDEBAR ROWS ARE DELETED FROM *HERE*
--------------------------------------------
Three of the four rail records are declared by `pb_sidebar`, not by this
module. The cleanup lives with the module that deleted the ACTIONS, because
that is the module whose version changed and therefore the only one whose
migration runs — and because the debt is ours: pb_sidebar's records were
correct until we removed what they pointed at.

DELIBERATELY NOT TOUCHED
------------------------
`hr.workforce.dashboard` (the Python transient) survives, and so do its access
rows: `pb_business_trip` still `_inherit`s it, and that module is outside this
phase's scope — a LIVE caller means keep and report (P7 §1 WP-3). Its VIEW,
server action, act_window and menu are gone, so nothing opens it any more.
`hr.attendance.timecard` and `hr.shift.planning.grid` also survive by design:
the Time hub's Timeline and `pb_schedule` read those facades server-side.

IDEMPOTENT: every statement is a DELETE keyed on `ir_model_data`, so a second
run finds nothing and removes nothing.
"""

import logging

_logger = logging.getLogger(__name__)

# (module, name) of every ir_model_data row whose record must go.
_DEAD = [
    # --- the client/server/window actions and the view behind the dashboard --
    ('pb_hr_workforce', 'action_shift_planning_grid'),
    ('pb_hr_workforce', 'action_attendance_live'),
    ('pb_hr_workforce', 'action_attendance_timecard'),
    ('pb_hr_workforce', 'action_overtime_rules_dashboard'),
    ('pb_hr_workforce', 'action_workforce_dashboard_server'),
    ('pb_hr_workforce', 'action_workforce_dashboard'),
    ('pb_hr_workforce', 'view_workforce_dashboard_form'),
    # --- the native menu entries that opened them --------------------------
    ('pb_hr_workforce', 'menu_workforce_dashboard'),
    ('pb_hr_workforce', 'menu_attendance_live'),
    ('pb_hr_workforce', 'menu_attendance_timecard'),
    ('pb_hr_workforce', 'menu_shift_planning'),
    # --- the legacy pb_hr_flow launcher menu (its ACTION stays: three live
    #     callers open `pb_hr_flow.action_hr_flow_wizard` directly) ----------
    ('pb_hr_flow', 'menu_hr_workflow_flow'),
    # --- the retired rail entries that pointed at the four dead cockpits ----
    ('pb_sidebar', 'item_wf_dashboard'),
    ('pb_sidebar', 'item_wf_live'),
    ('pb_sidebar', 'item_wf_timecards'),
    ('pb_sidebar', 'item_wf_overtime'),
]

# The model each xmlid's table lives in, so the row itself goes too — deleting
# only `ir_model_data` would orphan the record and leave the rail rendering it.
_TABLES = {
    'ir.actions.client': 'ir_act_client',
    'ir.actions.server': 'ir_act_server',
    'ir.actions.act_window': 'ir_act_window',
    'ir.ui.view': 'ir_ui_view',
    'ir.ui.menu': 'ir_ui_menu',
    'pb.sidebar.item': 'pb_sidebar_item',
}


def migrate(cr, version):
    removed = []
    for module, name in _DEAD:
        cr.execute("""
            SELECT id, model, res_id FROM ir_model_data
             WHERE module = %s AND name = %s
        """, (module, name))
        row = cr.fetchone()
        if not row:
            continue                      # already gone, or never installed
        imd_id, model, res_id = row
        table = _TABLES.get(model)
        if table:
            # `ir.actions.*` rows carry a shadow row in `ir_actions`; the FK is
            # ON DELETE CASCADE from the concrete table, so one DELETE is
            # enough and doing it the other way round would strand the child.
            cr.execute('DELETE FROM %s WHERE id = %%s' % table, (res_id,))
        else:                             # pragma: no cover - unknown model
            _logger.warning(
                'pb_hr_workforce P7: %s.%s is a %s, which this migration does '
                'not know how to delete — the ir_model_data row is removed but '
                'the record survives.', module, name, model)
        cr.execute('DELETE FROM ir_model_data WHERE id = %s', (imd_id,))
        removed.append('%s.%s' % (module, name))

    # A menu whose action went with it would still render as an empty branch.
    cr.execute("""
        DELETE FROM ir_ui_menu
         WHERE action IS NOT NULL
           AND split_part(action, ',', 1) IN
               ('ir.actions.client', 'ir.actions.server', 'ir.actions.act_window')
           AND NOT EXISTS (
               SELECT 1 FROM ir_actions a
                WHERE a.id = split_part(action, ',', 2)::integer)
    """)
    orphan_menus = cr.rowcount

    _logger.info(
        'pb_hr_workforce P7: buried %s legacy record(s): %s. %s orphaned '
        'menu(s) swept.', len(removed), ', '.join(removed) or 'none',
        orphan_menus)
