# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P1a — T3: the sidebar swap, asserted in the DATABASE.

W13.1, learned the hard way in P0: a repo-only sidebar "fix" is indistinguishable
from a real one unless something reads the database back. `ir_model_data.noupdate`
is a per-record column that Odoo never refreshes, so a data file can say one
thing while the live record says another and `-u` reports EXIT 0 either way.

Every assertion below therefore resolves the xmlid and reads the RECORD, after
the upgrade — never the XML.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTimeHubSidebar(TransactionCase):

    def _item(self, xmlid):
        # active_test=False: a retired item still exists, and its `active` value
        # is exactly what we are here to check.
        rec = self.env.ref(xmlid, raise_if_not_found=False)
        if rec:
            return rec.with_context(active_test=False)
        return rec

    def _section(self):
        if 'pb.sidebar.item' not in self.env:
            self.skipTest('pb_sidebar is not installed')
        sec = self.env.ref('pb_sidebar.sec_workforce', raise_if_not_found=False)
        if not sec:
            self.skipTest('the Workforce sidebar section is not installed')
        return sec

    # ------------------------------------------------------------------ new
    # UPDATED BY P3a: the hub is now the Time LENS of Mission Control, so its
    # rail entry joined the 900 retired band (W18) — the shell's single
    # "Workforce" item owns the live sequence now. The RECORD is still P1a's and
    # still has to be correct, because retirement is reversible.
    def test_time_item_is_retired_in_the_900_band(self):
        item = self._item('pb_time_hub.item_wf_time')
        self.assertTrue(item, 'the Time sidebar item must exist')
        self.assertFalse(item.active, 'the Time hub is a lens now, not a rail item')
        self.assertEqual(item.sequence, 908)
        self.assertEqual(item.action_tag, 'pb_time_hub')
        self.assertEqual(item.icon, 'clock')
        self.assertEqual(item.section_id, self._section())

    def test_the_time_hub_action_survives_its_retirement(self):
        """P3a retires rail entries, never actions: the standalone hub is still
        reachable, and Today's own hand-off falls back to it when the board is
        NOT inside the shell."""
        act = self.env.ref('pb_time_hub.action_pb_time_hub', raise_if_not_found=False)
        self.assertTrue(act, 'the Time hub action must survive P3a')
        self.assertEqual(act.tag, 'pb_time_hub')

    def test_time_item_carries_the_officer_gate(self):
        """Officer-and-up, matching the Weekly Entry persona it inherits and
        the pb.time.hub facade's own gate (W8: rail gate == surface gate). The
        record keeps it so it stays re-enable-able, and Mission Control asks the
        same question client-side before offering the Time lens."""
        item = self._item('pb_time_hub.item_wf_time')
        officer = self.env.ref('hr_attendance.group_hr_attendance_officer')
        # CONTAINS, not EQUALS (P6): a rail gate is a floor, not an inventory.
        # `pb_demo._pb_demo_rewire` joins "Payobook Demo User" onto every gated
        # item on a demo database, so equality here asserts which modules are
        # installed rather than that the officer gate is in place.
        self.assertIn(officer.id, item.groups_id.ids,
                      'the Time item must require the attendance officer group')

    # -------------------------------------------------------------- retired
    def test_the_three_absorbed_items_are_deactivated(self):
        """Timecards / Weekly Entry / Attendance Control leave the rail.

        Attendance Control is the interesting one: its data file was
        noupdate="1", so this assertion is what proves the W13.1 migration
        actually ran rather than the file merely claiming a new value.
        """
        expected = {
            'pb_sidebar.item_wf_timecards': 'Timecards',
            'pb_hr_workforce.item_wf_weekentry': 'Weekly Entry',
            'pb_attendance_flow.item_attendance_control': 'Attendance Control',
        }
        checked = 0
        for xmlid, label in expected.items():
            rec = self._item(xmlid)
            if not rec:
                continue
            checked += 1
            self.assertFalse(
                rec.active,
                '%s (%s) must be retired from the rail; it is still active — if '
                'the repo says otherwise, the declaring data file is probably '
                'still frozen in ir_model_data.noupdate (W13.1)' % (label, xmlid))
        self.assertEqual(checked, 3, 'all three retired items must be present to check')

    def test_attendance_control_record_is_no_longer_frozen(self):
        """The stored noupdate flag itself is cleared, so P1b can just edit the
        data file instead of shipping yet another migration."""
        rec = self.env.ref('pb_attendance_flow.item_attendance_control',
                           raise_if_not_found=False)
        if not rec:
            self.skipTest('pb_attendance_flow is not installed')
        imd = self.env['ir.model.data'].search([
            ('module', '=', 'pb_attendance_flow'),
            ('name', '=', 'item_attendance_control'),
        ], limit=1)
        self.assertTrue(imd)
        self.assertFalse(imd.noupdate,
                         'the P1a migration must clear the stored noupdate flag')

    # ------------------------------------------------------------- hygiene
    def test_workforce_sequences_are_still_unique(self):
        """W8, counting retired items too — a deactivated record still occupies
        its sequence the moment someone re-enables it. This is why Timecards had
        to move to the 900 retired band when the Time hub took 30."""
        sec = self._section()
        items = self.env['pb.sidebar.item'].with_context(active_test=False).search(
            [('section_id', '=', sec.id)])
        seqs = items.mapped('sequence')
        dupes = sorted({s for s in seqs if seqs.count(s) > 1})
        self.assertFalse(dupes, 'duplicated Workforce sequences: %s (%s)' % (
            dupes, ', '.join('%s=%s' % (i.name, i.sequence)
                             for i in items.sorted('sequence') if i.sequence in dupes)))

    def test_the_three_p1a_absorbed_items_stay_retired(self):
        """P1a's own contribution to the retired set, still retired.

        This test used to pin the retired set EXACTLY and assert a live count of
        12. P1b retired four more items (Workforce Dashboard, Live Attendance,
        Overtime Rules, Driver Tracking) and relocated Payroll Report, so an
        exact-set assertion here would now fail on work that is correct — and,
        worse, it would fail again on every future phase that retires anything.

        The durable question for THIS phase's test file is narrower and is the
        one P1a actually owns: did the three surfaces the Time hub absorbed stay
        off the rail? The whole-rail shape (8 live items, the complete retired
        set, the 900 band) is asserted where it belongs, by the phase that
        created it: pb_today/tests/test_sidebar.py.
        """
        sec = self._section()
        Item = self.env['pb.sidebar.item']
        live_ids = set(Item.search([('section_id', '=', sec.id)]).ids)

        checked = 0
        for xmlid in ('pb_sidebar.item_wf_timecards',
                      'pb_hr_workforce.item_wf_weekentry',
                      'pb_attendance_flow.item_attendance_control'):
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            if not rec:
                continue
            checked += 1
            self.assertNotIn(
                rec.id, live_ids,
                '%s was absorbed into the Time hub in P1a and must stay off the '
                'rail' % xmlid)
        self.assertEqual(checked, 3, 'all three absorbed items must be present')
