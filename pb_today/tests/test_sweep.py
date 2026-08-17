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
        driver map; the Time hub folded in three more. None of those actions may
        disappear in this phase — the retirement is the rail entry only."""
        for xmlid in (
            'pb_hr_workforce.action_attendance_live',
            'pb_hr_workforce.action_workforce_dashboard_server',
            'pb_hr_workforce.action_attendance_timecard',
            'pb_hr_workforce.action_overtime_rules_dashboard',
            'pb_hr_workforce.action_payroll_report_dashboard',
            'pb_driver_checkin.action_pb_driver_map',
            'pb_attendance_flow.action_pb_attendance_flow',
        ):
            self.assertTrue(
                self.env.ref(xmlid, raise_if_not_found=False),
                '%s was deleted — P1b retires rail entries, not actions' % xmlid)
