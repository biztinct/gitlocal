# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P3a — T2: the sidebar flip, asserted in the DATABASE.

Seven items become one. Every assertion here resolves the xmlid and reads the
RECORD after the upgrade, never the XML, because W13.1 has now bitten this
program three times: `ir_model_data.noupdate` is a per-record column Odoo never
refreshes, so a data file can say one thing while the live record says another
and `-u` reports EXIT 0 either way — no error, no warning, a perfectly healthy
log and a rail that never moved.

P3a is the first phase where SEVEN records have to move at once, spread over
seven data files in seven modules, so `test_no_workforce_record_is_frozen` reads
the flag on all of them rather than trusting the history.
"""
from odoo.tests import TransactionCase, tagged

# (xmlid, retired sequence). The Option-A rail, in the order it used to read.
_RETIRED_BY_P3A = [
    ('pb_today.item_wf_today', 906),
    ('pb_sidebar.item_wf_roster', 907),
    ('pb_time_hub.item_wf_time', 908),
    ('pb_timeoff.item_leave_center', 909),
    ('pb_hr_workforce.item_wf_ot_desk', 910),
    ('pb_business_trip.item_wf_trips', 911),
    ('pb_team.item_my_team', 912),
]

# Retired by P0/P1a/P1b/P2, still where those phases left them.
_RETIRED_BEFORE = [
    ('pb_sidebar.item_wf_timecards', 900),
    ('pb_sidebar.item_wf_dashboard', 901),
    ('pb_sidebar.item_wf_live', 902),
    ('pb_sidebar.item_wf_overtime', 903),
    ('pb_driver_checkin.item_driver_tracking', 904),
    ('pb_sidebar.item_wf_templates', 905),
    ('pb_attendance_flow.item_attendance_control', 25),
    ('pb_hr_workforce.item_wf_weekentry', 35),
]

# The seven cockpit actions the shell absorbs. Retirement is `active = False`,
# never deletion — every one of these stays openable on its own URL.
_ABSORBED_ACTIONS = (
    'pb_today.action_pb_today',
    'pb_schedule.action_pb_schedule',
    'pb_time_hub.action_pb_time_hub',
    'pb_timeoff.action_pb_timeoff',
    'pb_hr_workforce.action_pb_ot_desk',
    'pb_business_trip.action_pb_trips',
    'pb_team.action_pb_team',
)


@tagged('post_install', '-at_install')
class TestP3aSidebar(TransactionCase):

    def _item(self, xmlid):
        # active_test=False: a retired item still exists, and its `active` value
        # is exactly what we are here to check.
        rec = self.env.ref(xmlid, raise_if_not_found=False)
        return rec.with_context(active_test=False) if rec else rec

    def _section(self, name='pb_sidebar.sec_workforce'):
        if 'pb.sidebar.item' not in self.env:
            self.skipTest('pb_sidebar is not installed')
        sec = self.env.ref(name, raise_if_not_found=False)
        if not sec:
            self.skipTest('%s is not installed' % name)
        return sec

    # ==================================================== the one live item
    def test_the_workforce_section_is_exactly_one_item(self):
        """The whole point of the phase, read back off the rail."""
        sec = self._section()
        live = self.env['pb.sidebar.item'].search([('section_id', '=', sec.id)])
        self.assertEqual(
            len(live), 1,
            'expected ONE live Workforce item, found %s: %s' % (
                len(live), ', '.join('%s(%s)' % (i.name, i.sequence)
                                     for i in live.sorted('sequence'))))
        item = live
        self.assertEqual(item.name, 'Workforce')
        self.assertEqual(item.sequence, 10)
        self.assertEqual(item.icon, 'compass')
        self.assertEqual(item.action_xmlid, 'pb_mission.action_pb_workforce')
        self.assertEqual(item.action_tag, 'pb_workforce')
        self.assertEqual(item, self._item('pb_mission.item_workforce'))

    def test_the_shell_action_exists_and_is_a_client_action(self):
        act = self.env.ref('pb_mission.action_pb_workforce', raise_if_not_found=False)
        self.assertTrue(act, 'the Mission Control client action must exist')
        self.assertEqual(act._name, 'ir.actions.client')
        self.assertEqual(act.tag, 'pb_workforce')
        self.assertEqual(act.name, 'Workforce')

    def test_the_rail_item_still_lights_up_for_the_absorbed_cockpits(self):
        """W18 is a retirement, not a deletion: the seven client actions are
        still reachable, and opening one directly must highlight Workforce
        rather than leaving the rail with nothing selected.

        `pb_sidebar._resolveActive` matches xml_id -> tag -> res_model with
        last-writer-wins; with exactly ONE live Workforce item there is nothing
        to collide with.
        """
        item = self._item('pb_mission.item_workforce')
        if not item:
            self.skipTest('pb_mission is not installed')
        tags = {t.strip() for t in (item.match_action_tags or '').split(',')}
        for tag in ('pb_today', 'pb_schedule', 'pb_time_hub', 'pb_timeoff',
                    'pb_ot_desk', 'pb_trips', 'pb_team', 'pb_workforce'):
            self.assertIn(tag, tags, '%s must still light the Workforce item' % tag)

    # ======================================================== the retirement
    def test_the_seven_moved_into_the_900_band(self):
        """W18: `active = False` takes an item off the rail but not out of the
        section. The shell takes sequence 10, so the record that held it had to
        MOVE — and so did the other six, because the retired set has to stay
        internally unique too."""
        checked = 0
        for xmlid, seq in _RETIRED_BY_P3A:
            rec = self._item(xmlid)
            if not rec:
                continue
            checked += 1
            self.assertFalse(
                rec.active,
                '%s must be off the rail; it is still active — if the repo says '
                'otherwise, suspect a frozen ir_model_data.noupdate (W13.1)'
                % xmlid)
            self.assertEqual(rec.sequence, seq, '%s retired sequence' % xmlid)
        self.assertEqual(checked, 7, 'all seven retired items must be present')

    def test_the_retired_set_is_exactly_the_expected_fifteen(self):
        sec = self._section()
        Item = self.env['pb.sidebar.item']
        every = Item.with_context(active_test=False).search([('section_id', '=', sec.id)])
        live = Item.search([('section_id', '=', sec.id)])
        retired = every - live

        expected = {
            self.env.ref(x).id
            for x, _seq in (_RETIRED_BY_P3A + _RETIRED_BEFORE)
            if self.env.ref(x, raise_if_not_found=False)
        }
        self.assertEqual(len(expected), 15,
                         'the full Workforce module set must be installed')
        self.assertEqual(
            set(retired.ids), expected,
            'retired set was %s' % ', '.join(
                '%s(%s)' % (i.name, i.sequence) for i in retired.sorted('sequence')))

    def test_no_workforce_record_is_frozen(self):
        """W13.1/W27, checked on ALL of them rather than trusted from history.

        This phase moves seven records across seven data files in one upgrade.
        Any one of them still carrying a stored `noupdate` would be skipped by
        the loader in silence, and the only visible symptom would be a rail item
        that did not move.
        """
        pairs = [tuple(x.split('.', 1)) for x, _seq in _RETIRED_BY_P3A]
        pairs.append(('pb_mission', 'item_workforce'))
        frozen = []
        checked = 0
        for module, name in pairs:
            imd = self.env['ir.model.data'].search([
                ('module', '=', module), ('name', '=', name),
            ], limit=1)
            if not imd:
                continue
            checked += 1
            if imd.noupdate:
                frozen.append('%s.%s' % (module, name))
        self.assertTrue(checked, 'no Workforce sidebar record found at all')
        self.assertFalse(
            frozen,
            'these records are frozen — `-u` applies nothing to them and says '
            'nothing about it (W13.1): %s' % frozen)

    def test_every_absorbed_action_is_still_registered(self):
        """Nothing is deleted (binding non-goal). The lenses ARE these actions'
        components, and the standalone doors must keep working — Today's own
        hand-off fallback still calls one of them."""
        for xmlid in _ABSORBED_ACTIONS:
            self.assertTrue(
                self.env.ref(xmlid, raise_if_not_found=False),
                '%s was deleted — P3a retires rail entries, not actions' % xmlid)

    def test_retired_items_keep_their_actions(self):
        """A retired item pointing at a deleted action would turn the
        re-enable-it promise into a lie."""
        sec = self._section()
        retired = self.env['pb.sidebar.item'].with_context(active_test=False).search(
            [('section_id', '=', sec.id), ('active', '=', False)])
        self.assertTrue(retired)
        bad = [
            '%s -> %s' % (i.name, i.action_xmlid) for i in retired
            if i.action_xmlid
            and not self.env.ref(i.action_xmlid, raise_if_not_found=False)
        ]
        self.assertFalse(bad, '\n'.join(bad))

    # ============================================================= hygiene
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
        """W28 — a label is unique across the WHOLE sidebar, not per section.
        "Workforce" is a new label on this table (the string already existed on
        the pb.sidebar.SECTION and on an unrelated security group, neither of
        which shares it), so it needs the same database-wide check every rename
        in this program has had."""
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

    def test_the_workforce_icon_exists_in_the_fixed_sidebar_set(self):
        """The rail's icons are a FIXED inline Lucide set in pb_sidebar.js; an
        unknown name renders a plain circle, silently."""
        import os
        import re

        from odoo.modules.module import get_module_path
        path = os.path.join(get_module_path('pb_sidebar'), 'static', 'src', 'js',
                            'pb_sidebar.js')
        with open(path, encoding='utf-8') as fh:
            body = fh.read()
        block = re.search(r'const ICONS = \{(.*?)\n\};', body, re.S)
        self.assertTrue(block, 'could not find the ICONS set in pb_sidebar.js')
        known = set(re.findall(r'^\s{4}"?([A-Za-z0-9_-]+)"?\s*:', block.group(1), re.M))
        self.assertIn('compass', known)

        items = self.env['pb.sidebar.item'].with_context(active_test=False).search([])
        missing = sorted({i.icon for i in items if i.icon and i.icon not in known})
        self.assertFalse(missing, 'sidebar icons with no path in the fixed set '
                                  '(they render as plain circles): %s' % missing)
