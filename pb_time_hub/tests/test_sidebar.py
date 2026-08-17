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
    def test_time_item_is_live_at_sequence_30(self):
        item = self._item('pb_time_hub.item_wf_time')
        self.assertTrue(item, 'the Time sidebar item must exist')
        self.assertTrue(item.active, 'the Time hub must be ON the rail')
        self.assertEqual(item.sequence, 30)
        self.assertEqual(item.action_tag, 'pb_time_hub')
        self.assertEqual(item.icon, 'clock')
        self.assertEqual(item.section_id, self._section())

    def test_time_item_carries_the_officer_gate(self):
        """Officer-and-up, matching the Weekly Entry persona it inherits and
        the pb.time.hub facade's own gate (W8: rail gate == surface gate)."""
        item = self._item('pb_time_hub.item_wf_time')
        officer = self.env.ref('hr_attendance.group_hr_attendance_officer')
        self.assertEqual(item.groups_id.ids, officer.ids,
                         'the Time item must require exactly the attendance officer group')

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

    def test_workforce_section_is_down_to_twelve_visible_items(self):
        """14 before P1a, minus the 3 absorbed, plus Time = 12 (handover T15).

        Asserted two ways so the count survives a deployment that happens not to
        install every Workforce cockpit: the retired SET is pinned exactly, and
        the 12 is asserted only when the full 15-record section is present.
        """
        sec = self._section()
        Item = self.env['pb.sidebar.item']
        every = Item.with_context(active_test=False).search([('section_id', '=', sec.id)])
        live = Item.search([('section_id', '=', sec.id)])
        retired = every - live

        expected_retired = {
            self.env.ref(x).id for x in (
                'pb_sidebar.item_wf_timecards',
                'pb_hr_workforce.item_wf_weekentry',
                'pb_attendance_flow.item_attendance_control',
            ) if self.env.ref(x, raise_if_not_found=False)
        }
        self.assertEqual(
            set(retired.ids), expected_retired,
            'exactly the three absorbed items may be retired; retired set was %s'
            % ', '.join('%s(%s)' % (i.name, i.sequence) for i in retired))

        if len(every) == 15:
            self.assertEqual(
                len(live), 12,
                'expected 12 live Workforce items after P1a, found %s: %s' % (
                    len(live), ', '.join('%s(%s)' % (i.name, i.sequence)
                                         for i in live.sorted('sequence'))))
