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

    # ============================================= the Option-A rail, final
    def test_the_rail_is_exactly_seven_items_in_order(self):
        """P2's finale (§3.14 of the roadmap): Today · Schedule · Time ·
        Time Off · Overtime · Trips · Team Approvals. Shift Templates folded
        into Schedule's drawer and left the rail."""
        sec = self._section()
        live = self.env['pb.sidebar.item'].search([('section_id', '=', sec.id)])
        self.assertEqual(
            [i.name for i in live.sorted('sequence')],
            ['Today', 'Schedule', 'Time', 'Time Off', 'Overtime', 'Trips',
             'Team Approvals'],
            'the rail reads: %s' % ', '.join(
                '%s(%s)' % (i.name, i.sequence) for i in live.sorted('sequence')))
        self.assertEqual(len(live), 7)

    def test_shift_templates_retired_into_the_900_band(self):
        """W18: `active = False` takes an item off the rail but not out of the
        section, so 80 is only free once the record has MOVED."""
        item = self._item('pb_sidebar.item_wf_templates')
        if not item:
            self.skipTest('pb_sidebar is not installed')
        self.assertFalse(item.active, 'Shift Templates must be off the rail')
        self.assertEqual(item.sequence, 905)

    def test_the_shift_template_action_survives_its_retirement(self):
        """The drawer opens the native FORM, and the list action stays reachable
        — P2 deletes nothing (binding non-goal)."""
        act = self.env.ref('pb_hr_workforce.action_shift_template',
                           raise_if_not_found=False)
        self.assertTrue(act)
        search = self.env.ref('pb_schedule.view_shift_template_search',
                              raise_if_not_found=False)
        self.assertTrue(search, 'P2 owes hr.shift.template the search view it '
                                'never had (§3.9)')
        self.assertEqual(search.model, 'hr.shift.template')

    # ======================================== §3.10 hero-title alignment
    def test_the_cockpit_actions_are_named_like_the_rail(self):
        """A cockpit whose breadcrumb calls itself something the sidebar has
        never heard of makes the user re-derive where they are on arrival."""
        expected = {
            'pb_schedule.action_pb_schedule': 'Schedule',
            'pb_team.action_pb_team': 'Team Approvals',
            'pb_timeoff.action_pb_timeoff': 'Time Off',
            'pb_hr_workforce.action_pb_ot_desk': 'Overtime',
        }
        for xmlid, name in expected.items():
            act = self.env.ref(xmlid, raise_if_not_found=False)
            if not act:
                continue
            self.assertEqual(act.name, name, '%s should be named %r' % (xmlid, name))

    def test_the_hero_eyebrows_say_what_the_rail_says(self):
        """The RECORD is not enough — the eyebrow is a literal in the OWL
        template, and only reading the file catches a half-done rename."""
        import os

        from odoo.modules.module import get_module_path
        checks = [
            ('pb_schedule', ('static', 'src', 'xml', 'pb_schedule.xml'),
             '>Schedule<', 'My Roster'),
            ('pb_team', ('static', 'src', 'xml', 'pb_team.xml'),
             'Team Approvals', '>My Team<'),
            ('pb_timeoff', ('static', 'src', 'xml', 'pb_timeoff.xml'),
             'Time Off', '/> Leave</div>'),
            ('pb_hr_workforce', ('static', 'src', 'xml', 'pb_ot_desk.xml'),
             '/> Overtime</div>', '/> Overtime Desk</div>'),
        ]
        for module, parts, needle, gone in checks:
            path = get_module_path(module)
            if not path:
                continue
            full = os.path.join(path, *parts)
            if not os.path.exists(full):
                continue
            with open(full, encoding='utf-8') as fh:
                body = fh.read()
            self.assertIn(needle, body, '%s hero title' % module)
            self.assertNotIn(gone, body, '%s still carries the old title' % module)

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
