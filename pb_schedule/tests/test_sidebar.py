# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P2 — T6: the rail, asserted in the DATABASE.

W13.1, learned three times now: a repo-only sidebar change is indistinguishable
from a real one unless something reads the record back. `ir_model_data.noupdate`
is a per-record column Odoo never refreshes, so a data file can say one thing
while the live record says another and `-u` reports EXIT 0 either way.

Every assertion here resolves the xmlid and reads the RECORD, after the upgrade.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestP2Sidebar(TransactionCase):

    def _item(self, xmlid):
        rec = self.env.ref(xmlid, raise_if_not_found=False)
        return rec.with_context(active_test=False) if rec else rec

    def _section(self, name='pb_sidebar.sec_workforce'):
        if 'pb.sidebar.item' not in self.env:
            self.skipTest('pb_sidebar is not installed')
        sec = self.env.ref(name, raise_if_not_found=False)
        if not sec:
            self.skipTest('%s is not installed' % name)
        return sec

    # ========================================================== the repoint
    def test_schedule_points_at_the_new_cockpit(self):
        item = self._item('pb_sidebar.item_wf_roster')
        if not item:
            self.skipTest('pb_sidebar is not installed')
        self.assertTrue(item.active)
        self.assertEqual(item.name, 'Schedule')
        self.assertEqual(item.sequence, 20)
        self.assertEqual(item.action_xmlid, 'pb_schedule.action_pb_schedule',
                         'the rail must open the P2 cockpit, not the legacy grid')
        self.assertEqual(item.action_tag, 'pb_schedule')

    def test_the_legacy_grid_still_lights_the_rail_item(self):
        """W18 is a retirement, not a deletion: the old client action is still
        registered and still reachable, and it must highlight Schedule rather
        than leaving the rail with nothing selected."""
        item = self._item('pb_sidebar.item_wf_roster')
        if not item:
            self.skipTest('pb_sidebar is not installed')
        tags = [t.strip() for t in (item.match_action_tags or '').split(',')]
        self.assertIn('shift_planning_grid', tags)
        self.assertIn('pb_schedule', tags)

    def test_the_legacy_action_is_still_registered(self):
        """A bookmark or a stray doAction must not 404 while the old screen
        exists (binding non-goal: no deletion in P2)."""
        act = self.env.ref('pb_hr_workforce.action_shift_planning_grid',
                           raise_if_not_found=False)
        self.assertTrue(act, 'the legacy Shift Roster action must survive P2')
        self.assertEqual(act.tag, 'shift_planning_grid')

    def test_the_rail_gate_matches_the_facade_gate(self):
        """W8: `hr.shift.planning.grid._require_officer` refuses anyone below
        attendance officer, so the rail must not advertise the cockpit to
        someone who would only get an AccessError."""
        item = self._item('pb_sidebar.item_wf_roster')
        if not item:
            self.skipTest('pb_sidebar is not installed')
        officer = self.env.ref('hr_attendance.group_hr_attendance_officer')
        self.assertEqual(item.groups_id.ids, officer.ids)

    def test_workforce_sequences_are_still_unique(self):
        """W8/W18, counting retired items too."""
        sec = self._section()
        items = self.env['pb.sidebar.item'].with_context(active_test=False).search(
            [('section_id', '=', sec.id)])
        seqs = items.mapped('sequence')
        dupes = sorted({s for s in seqs if seqs.count(s) > 1})
        self.assertFalse(dupes, 'duplicated Workforce sequences: %s (%s)' % (
            dupes, ', '.join('%s=%s' % (i.name, i.sequence)
                             for i in items.sorted('sequence')
                             if i.sequence in dupes)))

    def test_no_two_sidebar_items_share_a_label(self):
        """W28 — a label is unique across the WHOLE sidebar, not per section."""
        items = self.env['pb.sidebar.item'].search([])
        seen = {}
        for item in items:
            seen.setdefault((item.name or '').strip().lower(), []).append(item)
        dupes = {k: v for k, v in seen.items() if k and len(v) > 1}
        self.assertFalse(
            dupes,
            'two live sidebar items share a label:\n%s' % '\n'.join(
                '%r -> %s' % (k, ', '.join(
                    '%s/%s(seq %s)' % (i.section_id.technical_key, i.name,
                                       i.sequence) for i in v))
                for k, v in dupes.items()))
