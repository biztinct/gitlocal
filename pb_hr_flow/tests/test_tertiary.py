# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P7 — the legacy launcher's tertiary map, gated for the first time.

`hr.flow.wizard.get_tertiary_action` is the server-side resolver behind every
tile in the old pb_hr_flow launcher: the client sends a route key, the wizard
looks it up in a ~100-entry dict of xmlids and returns a full action for
`doAction`. It had NO tests at all — this module had no `tests/` package — which
is why five of its keys were able to point at deleted cockpits without anything
noticing.

THE FAILURE MODE THIS EXISTS FOR, stated precisely, because it is why a map like
this needs a gate more than most code does:

    action_xmlid, menu_xmlid = mapping.get(key, (False, False))
    if not action_xmlid:
        return {'type': 'ir.actions.act_window_close', 'context': {}}
    ...
    try:
        action = self.env['ir.actions.actions'].sudo()._for_xml_id(action_xmlid)
    except Exception:
        return {'type': 'ir.actions.act_window_close', 'context': {}}

Both arms are DELIBERATE and both are silent. The map is full of xmlids from
optional modules (`pb_hr_workforce_planning`, `pb_hr_payroll_vietnam`,
`ohrms_overtime`, `hr_shift`), and a launcher that raised on a database where
one of them is absent would be worse than one that does nothing. The cost is
that a key pointing at a DELETED action is indistinguishable from a key pointing
at an uninstalled module: the tile renders, the user clicks, the screen does not
change. No traceback, no console message, nothing in the log.

So the tests below never assert on the mapping literal. Two of them drive the
REAL resolver and compare the action it returns against the record it should
have found — the only form of the question the fallback cannot swallow — and one
is a plain source gate for the five xmlids that must never come back.
"""

import os

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

# The keys P7 remapped when it deleted the Gen-0 cockpits, and the surface each
# one now opens. Spelled out here rather than derived from the map, so a future
# edit to the map has to come and change this table too.
_REMAPPED = {
    'wf-dashboard': 'pb_today.action_pb_today',
    'wf-live-attendance': 'pb_today.action_pb_today',
    'wf-timecards': 'pb_time_hub.action_pb_time_hub',
    'wf-shift-roster': 'pb_schedule.action_pb_schedule',
    'wf-overtime-rules': 'pb_hr_workforce.action_pb_ot_desk',
}

# The one Workforce key P7 did NOT touch: that cockpit is alive, it is on the
# Pay Run rail, and pb_payruns' kanban opens it.
_KEPT = {'wf-payroll-report': 'pb_hr_workforce.action_payroll_report_dashboard'}

# The actions the deletion removed. A tile may never name one again.
_DELETED = (
    'pb_hr_workforce.action_workforce_dashboard_server',
    'pb_hr_workforce.action_attendance_live',
    'pb_hr_workforce.action_attendance_timecard',
    'pb_hr_workforce.action_shift_planning_grid',
    'pb_hr_workforce.action_overtime_rules_dashboard',
)


@tagged('post_install', '-at_install')
class TestTertiaryMap(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env['hr.flow.wizard']

    def _resolve(self, key):
        """What the launcher's client gets back for one tile."""
        return self.Wizard.get_tertiary_action(key)

    # ------------------------------------------------------------ the remap
    def test_the_remapped_tiles_open_the_surface_that_absorbed_them(self):
        """Asserted through the resolver and against the RECORD, not against
        the dict: the identity of the action that comes back is the only thing
        that proves the tile works."""
        checked = 0
        for key, xmlid in _REMAPPED.items():
            target = self.env.ref(xmlid, raise_if_not_found=False)
            if not target:
                continue           # that module is not on this database
            action = self._resolve(key)
            self.assertIsInstance(action, dict)
            self.assertNotEqual(
                action.get('type'), 'ir.actions.act_window_close',
                '%s fell through to the silent fallback even though %s exists'
                % (key, xmlid))
            self.assertEqual(
                action.get('id'), target.id,
                '%s opened %r instead of %s'
                % (key, action.get('name'), xmlid))
            checked += 1
        self.assertTrue(
            checked, 'none of the remap targets is installed — this suite '
                     'proved nothing on this database')

    def test_the_payroll_report_tile_was_left_alone(self):
        """That cockpit is alive; remapping it would have retired a working
        surface for tidiness."""
        for key, xmlid in _KEPT.items():
            target = self.env.ref(xmlid, raise_if_not_found=False)
            if not target:
                self.skipTest('%s is not installed' % xmlid)
            self.assertEqual(self._resolve(key).get('id'), target.id)

    def test_no_tile_names_a_cockpit_p7_deleted(self):
        """A SOURCE gate, deliberately, and it is the cheap half of the pair
        above. The resolver cannot tell us this: a key naming a deleted action
        returns exactly the same `act_window_close` as a key naming an
        uninstalled one, so behaviour alone can never say "this entry is
        wrong", only "this entry did nothing". Reading the file can.
        """
        path = get_module_path('pb_hr_flow')
        self.assertTrue(path, 'pb_hr_flow has no module path')
        full = os.path.join(path, 'models', 'hr_flow_wizard.py')
        with open(full, encoding='utf-8') as fh:
            body = fh.read()
        # The prose above the map explains the deletion and legitimately names
        # the cockpits, so only a QUOTED map value counts — W48's corollary
        # (a word-shaped gate fails on its own documentation).
        bad = [x for x in _DELETED if "'%s'" % x in body]
        self.assertFalse(
            bad,
            'the tertiary map points at actions deleted in P7; each renders a '
            'tile that answers a click with silence:\n%s' % '\n'.join(bad))

    # ------------------------------------------------------- the whole map
    def test_every_tile_whose_module_is_installed_resolves(self):
        """The sweep, over the routes the launcher's own UI offers.

        Only entries whose MODULE is installed can be judged: a missing optional
        module is a supported state that the fallback exists for, while a
        missing xmlid inside an installed module is a dead tile.
        """
        Module = self.env['ir.module.module'].sudo()
        installed = set(
            Module.search([('state', '=', 'installed')]).mapped('name'))
        dead = []
        for key in _WORKFORCE_ROUTES:
            action = self._resolve(key)
            if action.get('type') != 'ir.actions.act_window_close':
                continue
            dead.append(key)
        self.assertFalse(
            dead,
            'these Workforce tiles resolve to nothing on a database where '
            'their modules are installed (%s):\n%s'
            % (', '.join(sorted(installed & _WORKFORCE_MODULES)),
               '\n'.join(dead)))

    def test_an_unknown_key_is_a_no_op_rather_than_a_traceback(self):
        """The fallback is documented behaviour and worth pinning: the launcher
        must survive a client sending a route it has never heard of."""
        action = self._resolve('no-such-route-at-all')
        self.assertEqual(action.get('type'), 'ir.actions.act_window_close')


# The Workforce tiles the launcher renders (hr_flow_hover.js, `attendance`
# group). Every one of them belongs to a module this repo ships and installs
# together, so unlike the payroll/leave entries they are all expected to
# resolve on any Payobook database.
_WORKFORCE_ROUTES = tuple(_REMAPPED) + tuple(_KEPT) + ('wf-shift-templates',)
_WORKFORCE_MODULES = {'pb_today', 'pb_time_hub', 'pb_schedule',
                      'pb_hr_workforce'}
