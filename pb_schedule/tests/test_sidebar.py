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
    # UPDATED BY P3a: Schedule is now a LENS of Mission Control, so this record
    # joined the 900 retired band (W18). P2's repoint still has to hold on it —
    # retirement is reversible, and the shell's Schedule lens is this cockpit.
    def test_schedule_points_at_the_new_cockpit(self):
        item = self._item('pb_sidebar.item_wf_roster')
        if not item:
            self.skipTest('pb_sidebar is not installed')
        self.assertFalse(item.active, 'Schedule is a shell lens now, not a rail item')
        self.assertEqual(item.name, 'Schedule')
        self.assertEqual(item.sequence, 907)
        self.assertEqual(item.action_xmlid, 'pb_schedule.action_pb_schedule',
                         'the rail must open the P2 cockpit, not the legacy grid')
        self.assertEqual(item.action_tag, 'pb_schedule')

    # UPDATED BY P7 (WP-3). These two used to assert the OPPOSITE of what
    # follows: that `pb_hr_workforce.action_shift_planning_grid` was still
    # registered, and that `item_wf_roster` still listed the legacy
    # `shift_planning_grid` tag so a bookmark into the Gen-0 grid would light
    # the Schedule rail item. Both were correct for P2, whose binding non-goal
    # was "no deletion" — and both became false the moment P7 deleted that
    # cockpit's JS, CSS and client action. A `match_action_tags` entry naming a
    # tag no longer in the browser's action registry can never be the active
    # one; keeping it asserted would have been a gate defending a screen that
    # does not exist.
    def test_the_rail_item_only_claims_tags_that_still_exist(self):
        """W71's rule from the other side: a match dimension is a CLAIM on a
        real surface. The legacy grid's tag is gone from the registry, so the
        list must not name it — otherwise the next reader believes there is a
        second Schedule screen somewhere."""
        item = self._item('pb_sidebar.item_wf_roster')
        if not item:
            self.skipTest('pb_sidebar is not installed')
        tags = [t.strip() for t in (item.match_action_tags or '').split(',')]
        self.assertIn('pb_schedule', tags)
        self.assertNotIn(
            'shift_planning_grid', tags,
            'the Gen-0 grid was deleted in P7 — a rail item may not claim a '
            'client tag that nothing registers')

    def test_the_legacy_grid_action_is_gone_but_the_facade_is_not(self):
        """The P7 deletion, asserted from the database (W13.1), and the line it
        stopped at.

        The client ACTION and its OWL component are deleted: nothing renders
        `shift_planning_grid` any more, so leaving the record would have left a
        door that can only ever produce an error (W29). The `hr.shift.planning
        .grid` MODEL is untouched and must stay untouched — `pb_schedule`
        inherits it and every one of this cockpit's reads and writes goes
        through it.
        """
        self.assertFalse(
            self.env.ref('pb_hr_workforce.action_shift_planning_grid',
                         raise_if_not_found=False),
            'the Gen-0 Shift Roster action survived P7 with no component '
            'behind it')
        self.assertIn(
            'hr.shift.planning.grid', self.env,
            'the grid FACADE must survive — pb_schedule is built on it')
        self.assertTrue(
            hasattr(self.env['hr.shift.planning.grid'], 'get_grid_data'),
            'the facade lost the method pb_schedule inherits')

    def test_the_rail_gate_matches_the_facade_gate(self):
        """W8: `hr.shift.planning.grid._require_officer` refuses anyone below
        attendance officer, so the rail must not advertise the cockpit to
        someone who would only get an AccessError."""
        item = self._item('pb_sidebar.item_wf_roster')
        if not item:
            self.skipTest('pb_sidebar is not installed')
        officer = self.env.ref('hr_attendance.group_hr_attendance_officer')
        # CONTAINS, not EQUALS (P6): `pb_demo._pb_demo_rewire` joins "Payobook
        # Demo User" onto every gated rail item on a demo database. The gate the
        # test is about is the FLOOR — that nobody below the officer tier is
        # offered a cockpit that would only give them an AccessError.
        self.assertIn(officer.id, item.groups_id.ids)

    # ============================================= the Option-A rail, final
    # REMOVED BY P3a: `test_the_rail_is_exactly_seven_items_in_order` asserted
    # P2's finale — Today · Schedule · Time · Time Off · Overtime · Trips · Team
    # Approvals. P3a folds all seven into the Mission Control shell, so the
    # whole-rail shape is now asserted by the phase that owns it,
    # pb_mission/tests/test_sidebar.py (one live item, fifteen retired).
    # Keeping it here would mean a red gate on work that is correct, and a red
    # gate nobody believes is the same as no gate.

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
