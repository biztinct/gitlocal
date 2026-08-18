# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P1b — T14: the automated half of the rail sweep.

Clicking eight rail entries by hand proves they open; this proves they still
POINT somewhere, on every future upgrade, without anybody clicking. Two rails
matter and they pull in opposite directions:

  * a LIVE item whose `action_xmlid` no longer resolves is a rail entry that
    throws when clicked — the failure mode a data-driven sidebar makes very easy
    (the action lives in another module's XML, and nothing links the two);
  * a RETIRED item's action must still EXIST. Retirement in this program means
    `active = False`, never deletion: the cockpits stay reachable by URL, an
    admin can re-enable a row, and the dead-code sweep is a later phase with its
    own doAction-caller audit. A retired item pointing at a deleted action would
    silently turn that promise into a lie.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWorkforceRailSweep(TransactionCase):

    def _section(self, xmlid='pb_sidebar.sec_workforce'):
        if 'pb.sidebar.item' not in self.env:
            self.skipTest('pb_sidebar is not installed')
        sec = self.env.ref(xmlid, raise_if_not_found=False)
        if not sec:
            self.skipTest('%s is not installed' % xmlid)
        return sec

    def _items(self, xmlid='pb_sidebar.sec_workforce', active=True):
        Item = self.env['pb.sidebar.item']
        if not active:
            Item = Item.with_context(active_test=False)
        items = Item.search([('section_id', '=', self._section(xmlid).id)])
        return items if active else items

    def test_every_live_workforce_item_points_at_a_real_action(self):
        bad = []
        for item in self._items():
            if not item.action_xmlid:
                # tag-only items are resolved client-side by the action registry
                self.assertTrue(
                    item.action_tag,
                    '%s has neither an action_xmlid nor an action_tag' % item.name)
                continue
            if not self.env.ref(item.action_xmlid, raise_if_not_found=False):
                bad.append('%s -> %s' % (item.name, item.action_xmlid))
        self.assertFalse(bad, 'live rail items pointing at a missing action:\n%s'
                         % '\n'.join(bad))

    def test_retired_items_keep_their_actions(self):
        """Retirement is `active = False`, never deletion (the program's rule
        and the reason the 900 band exists)."""
        Item = self.env['pb.sidebar.item'].with_context(active_test=False)
        sec = self._section()
        retired = Item.search([('section_id', '=', sec.id), ('active', '=', False)])
        self.assertTrue(retired, 'P1a and P1b both retired items; none found')
        bad = []
        for item in retired:
            if item.action_xmlid and not self.env.ref(
                    item.action_xmlid, raise_if_not_found=False):
                bad.append('%s -> %s' % (item.name, item.action_xmlid))
        self.assertFalse(
            bad,
            'a retired item lost its action — retirement must stay reversible '
            'and the cockpit URL-reachable:\n%s' % '\n'.join(bad))

    def test_payroll_report_is_reachable_from_the_pay_run_section(self):
        """The relocated item, swept from the other side: present, live, and
        pointing at the surviving dashboard action."""
        items = self._items('pb_sidebar.sec_payrun')
        report = items.filtered(lambda i: i.name == 'Payroll Report')
        self.assertTrue(report, 'Payroll Report must be live under Pay Run: %s'
                        % ', '.join(items.mapped('name')))
        self.assertTrue(self.env.ref(report.action_xmlid, raise_if_not_found=False))

    def test_the_today_action_resolves_and_is_a_client_action(self):
        act = self.env.ref('pb_today.action_pb_today', raise_if_not_found=False)
        self.assertTrue(act, 'the Today client action must exist')
        self.assertEqual(act._name, 'ir.actions.client')
        self.assertEqual(act.tag, 'pb_today')

    def test_the_absorbed_cockpits_are_still_reachable_by_url(self):
        """Today folded in Live Attendance, the Workforce Dashboard and the
        driver map; the Time hub folded in three more.

        UPDATED BY P7 (WP-3). This list used to include the four Gen-0 cockpits
        as well, under P1b's rule that "the retirement is the rail entry only".
        That rule had a shelf life: it is worth keeping an action reachable by
        URL only while something still RENDERS it. P7 deleted those four
        cockpits' JS and CSS, so their client actions were deleted with them —
        an `ir.actions.client` whose tag is not in the browser's action registry
        answers a bookmark with a broken screen, which is strictly worse than a
        404 (W29). What remains here is every absorbed action that still has a
        component behind it.
        """
        for xmlid in (
            'pb_hr_workforce.action_payroll_report_dashboard',
            'pb_driver_checkin.action_pb_driver_map',
            'pb_attendance_flow.action_pb_attendance_flow',
        ):
            self.assertTrue(
                self.env.ref(xmlid, raise_if_not_found=False),
                '%s was deleted — P1b retires rail entries, not actions' % xmlid)

    def test_the_gen0_cockpits_are_buried_rather_than_merely_retired(self):
        """The other half of the same decision, asserted in the DATABASE
        (W13.1) because a data-file deletion does not delete anything: the rows
        go in `pb_hr_workforce/migrations/19.0.4.14.0/post-migrate.py`.

        Two things have to be true at once, and the second is why this is a
        test rather than a grep. The ACTIONS are gone — nothing offers a screen
        that no longer exists. And the FACADES those cockpits sat on are not:
        `hr.attendance.timecard` feeds the Time hub's Timeline lens and
        `hr.shift.planning.grid` is what pb_schedule is built on, so deleting
        them with the UI would have taken two live surfaces down with the dead
        ones.
        """
        for xmlid in (
            'pb_hr_workforce.action_attendance_live',
            'pb_hr_workforce.action_workforce_dashboard_server',
            'pb_hr_workforce.action_attendance_timecard',
            'pb_hr_workforce.action_overtime_rules_dashboard',
            'pb_hr_workforce.action_shift_planning_grid',
        ):
            self.assertFalse(
                self.env.ref(xmlid, raise_if_not_found=False),
                '%s survived P7 with no component behind it' % xmlid)
        for model in ('hr.attendance.timecard', 'hr.shift.planning.grid'):
            self.assertIn(model, self.env,
                          '%s is a live facade and must not have been deleted'
                          % model)

    def test_the_rail_entries_went_with_the_cockpits_they_pointed_at(self):
        """`test_retired_items_keep_their_actions` above demands that every
        retired item's action still resolves. The four items that pointed at the
        deleted cockpits could not satisfy it and could not be repointed at
        anything honest, so they were deleted too — from the data file AND from
        the database."""
        if 'pb.sidebar.item' not in self.env:
            self.skipTest('pb_sidebar is not installed')
        for xmlid in ('pb_sidebar.item_wf_dashboard', 'pb_sidebar.item_wf_live',
                      'pb_sidebar.item_wf_timecards',
                      'pb_sidebar.item_wf_overtime'):
            self.assertFalse(
                self.env.ref(xmlid, raise_if_not_found=False),
                '%s still exists and points at a deleted action' % xmlid)
