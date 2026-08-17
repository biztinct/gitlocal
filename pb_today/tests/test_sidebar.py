# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P1b — T3: the IA finale, asserted in the DATABASE.

UPDATED BY P2: Shift Templates folded into Schedule's templates drawer, so the
rail is SEVEN items, not eight, and `item_wf_templates` joins the 900 retired
band. These gates are the DB-assert that catches a repo-only sidebar change, so
they are updated with the change rather than left red — a red gate nobody
believes is the same as no gate.

W13.1, learned the hard way in P0 and again in P1a: a repo-only sidebar "fix" is
indistinguishable from a real one unless something reads the database back.
`ir_model_data.noupdate` is a per-record column that Odoo never refreshes, so a
data file can say one thing while the live record says another and `-u` reports
EXIT 0 either way — no error, no warning, a healthy-looking log and an unchanged
rail.

Every assertion below therefore resolves the xmlid and reads the RECORD, after
the upgrade — never the XML. Business Trips is the one that matters most: its
data file was frozen until this phase, so if the migration did not run, exactly
one assertion here fails and names it.
"""
from odoo.tests import TransactionCase, tagged

# The Option-A rail, in full. (xmlid, label, sequence, icon)
_ACTIVE_RAIL = [
    ('pb_today.item_wf_today',            'Today',           10, 'activity'),
    ('pb_sidebar.item_wf_roster',         'Schedule',        20, 'calendar'),
    ('pb_time_hub.item_wf_time',          'Time',            30, 'clock'),
    ('pb_timeoff.item_leave_center',      'Time Off',        40, 'umbrella'),
    ('pb_hr_workforce.item_wf_ot_desk',   'Overtime',        50, 'zap'),
    ('pb_business_trip.item_wf_trips',    'Trips',           60, 'plane'),
    # "Team Approvals", not the handover's bare "Approvals":
    # pb_sidebar.item_approvals already owns that exact label in the OVERVIEW
    # section (the payroll payslip-run cockpit). See pb_team/data/pb_sidebar.xml.
    ('pb_team.item_my_team',              'Team Approvals',  70, 'inbox'),
    # P2: 'Shift Templates' (80) retired into Schedule's drawer -> 905, inactive
]

# Retired in P1b, parked in the 900 band (W18) — a deactivated item still
# OCCUPIES its sequence, and the new rail took 10, 20, 60, 70 and 80.
_RETIRED_900 = [
    ('pb_sidebar.item_wf_dashboard',           901),
    ('pb_sidebar.item_wf_live',                902),
    ('pb_sidebar.item_wf_overtime',            903),
    ('pb_driver_checkin.item_driver_tracking', 904),
    # P2 — folded into Schedule's templates drawer
    ('pb_sidebar.item_wf_templates',           905),
]

# Retired earlier, left where they were because nothing collides with them.
_RETIRED_INPLACE = [
    ('pb_sidebar.item_wf_timecards',              900),
    ('pb_attendance_flow.item_attendance_control', 25),
    ('pb_hr_workforce.item_wf_weekentry',          35),
]


@tagged('post_install', '-at_install')
class TestP1bSidebar(TransactionCase):

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

    # ============================================================ the rail
    def test_the_option_a_rail_is_exactly_what_the_handover_says(self):
        """Label, sequence, icon and active flag for all eight live items."""
        sec = self._section()
        checked = 0
        for xmlid, label, seq, icon in _ACTIVE_RAIL:
            rec = self._item(xmlid)
            if not rec:
                continue
            checked += 1
            self.assertTrue(rec.active, '%s must be ON the rail' % xmlid)
            self.assertEqual(rec.name, label, '%s label' % xmlid)
            self.assertEqual(rec.sequence, seq, '%s sequence' % xmlid)
            self.assertEqual(rec.icon, icon, '%s icon' % xmlid)
            self.assertEqual(rec.section_id, sec, '%s section' % xmlid)
        self.assertEqual(checked, len(_ACTIVE_RAIL),
                         'the whole Workforce rail must be installed to check it')

    def test_business_trips_is_no_longer_frozen(self):
        """The W13.1 unfreeze. If the migration did not run, `noupdate` is still
        true here and the sequence assertion above is still 37 — a repo-only
        change is indistinguishable from a real one without this read."""
        rec = self.env.ref('pb_business_trip.item_wf_trips', raise_if_not_found=False)
        if not rec:
            self.skipTest('pb_business_trip is not installed')
        imd = self.env['ir.model.data'].search([
            ('module', '=', 'pb_business_trip'),
            ('name', '=', 'item_wf_trips'),
        ], limit=1)
        self.assertTrue(imd)
        self.assertFalse(
            imd.noupdate,
            'the P1b migration must clear the stored noupdate flag — until it '
            'does, `-u pb_business_trip` applies nothing and says nothing')

    # ========================================================== retirement
    def test_the_retired_set_is_exactly_the_expected_one(self):
        sec = self._section()
        Item = self.env['pb.sidebar.item']
        every = Item.with_context(active_test=False).search([('section_id', '=', sec.id)])
        live = Item.search([('section_id', '=', sec.id)])
        retired = every - live

        expected = {
            self.env.ref(x).id
            for x, _seq in (_RETIRED_900 + _RETIRED_INPLACE)
            if self.env.ref(x, raise_if_not_found=False)
        }
        self.assertEqual(
            set(retired.ids), expected,
            'retired set was %s' % ', '.join(
                '%s(%s)' % (i.name, i.sequence) for i in retired.sorted('sequence')))

    def test_the_retirements_moved_into_the_900_band(self):
        """W18: `active = False` takes an item off the rail but not out of the
        section. Today took 10, Schedule 20, Trips 60 and Approvals 70 — so
        every item that held one of those had to MOVE, and P2's Shift Templates
        moved out of 80 for the same reason."""
        for xmlid, seq in _RETIRED_900:
            rec = self._item(xmlid)
            if not rec:
                continue
            self.assertFalse(rec.active, '%s must be off the rail' % xmlid)
            self.assertEqual(rec.sequence, seq, '%s retired sequence' % xmlid)

    def test_workforce_sequences_are_unique(self):
        """W8, counting retired items too."""
        sec = self._section()
        items = self.env['pb.sidebar.item'].with_context(active_test=False).search(
            [('section_id', '=', sec.id)])
        seqs = items.mapped('sequence')
        dupes = sorted({s for s in seqs if seqs.count(s) > 1})
        self.assertFalse(dupes, 'duplicated Workforce sequences: %s (%s)' % (
            dupes, ', '.join('%s=%s' % (i.name, i.sequence)
                             for i in items.sorted('sequence') if i.sequence in dupes)))

    def test_exactly_seven_workforce_items_are_live(self):
        """The sweep count: 14 items before P1a, 8 after P1b, SEVEN after P2 —
        the final Option-A shape."""
        sec = self._section()
        live = self.env['pb.sidebar.item'].search([('section_id', '=', sec.id)])
        self.assertEqual(
            len(live), 7,
            'expected 7 live Workforce items, found %s: %s' % (
                len(live), ', '.join('%s(%s)' % (i.name, i.sequence)
                                     for i in live.sorted('sequence'))))
        self.assertEqual(
            [i.name for i in live.sorted('sequence')],
            [label for _x, label, _s, _i in _ACTIVE_RAIL],
            'the rail must read Today · Schedule · Time · Time Off · Overtime · '
            'Trips · Team Approvals, in that order')

    # ============================================================ relocation
    def test_payroll_report_moved_to_the_pay_run_section_with_its_gate(self):
        """Salary aggregates by department are a PAYROLL surface that happened
        to live under Workforce. P0's gate travels with it (W8)."""
        rec = self._item('pb_sidebar.item_wf_payroll_report')
        if not rec:
            self.skipTest('pb_sidebar is not installed')
        self.assertTrue(rec.active)
        self.assertEqual(rec.section_id, self._section('pb_sidebar.sec_payrun'),
                         'Payroll Report must sit under Pay Run now')
        self.assertEqual(rec.sequence, 45)
        payroll_user = self.env.ref('om_hr_payroll.group_hr_payroll_user')
        self.assertEqual(
            rec.groups_id.ids, payroll_user.ids,
            'the relocation must not drop P0 gate — it exposes salary aggregates')

    def test_pay_run_sequences_are_unique_after_the_relocation(self):
        sec = self._section('pb_sidebar.sec_payrun')
        items = self.env['pb.sidebar.item'].with_context(active_test=False).search(
            [('section_id', '=', sec.id)])
        seqs = items.mapped('sequence')
        dupes = sorted({s for s in seqs if seqs.count(s) > 1})
        self.assertFalse(dupes, 'duplicated Pay Run sequences: %s (%s)' % (
            dupes, ', '.join('%s=%s' % (i.name, i.sequence)
                             for i in items.sorted('sequence') if i.sequence in dupes)))

    # ================================================================ gates
    def test_today_carries_the_officer_gate(self):
        rec = self._item('pb_today.item_wf_today')
        if not rec:
            self.skipTest('pb_today is not installed')
        officer = self.env.ref('hr_attendance.group_hr_attendance_officer')
        self.assertEqual(rec.groups_id.ids, officer.ids,
                         'the rail gate must match the pb.today facade gate (W8)')

    def test_no_two_live_rail_items_share_a_label(self):
        """W28 — a label is unique across the WHOLE sidebar, not per section.

        P1b's handover specified renaming "My Team" to "Approvals";
        `pb_sidebar.item_approvals` already carried exactly that label in the
        Overview section (the payroll payslip-run cockpit). W8 makes SEQUENCES
        unique within a section and nothing was checking labels — but a user
        reads labels, and two identical entries pointing at two different
        cockpits is a rail you cannot navigate. The collision is invisible in
        the data file you are editing, because the twin lives in another module,
        so it needs a database-wide test.
        """
        items = self.env['pb.sidebar.item'].search([])
        seen = {}
        for item in items:
            seen.setdefault((item.name or '').strip().lower(), []).append(item)
        dupes = {k: v for k, v in seen.items() if k and len(v) > 1}
        self.assertFalse(
            dupes,
            'two live sidebar items share a label:\n%s' % '\n'.join(
                '%r -> %s' % (k, ', '.join(
                    '%s/%s(seq %s)' % (i.section_id.technical_key, i.name, i.sequence)
                    for i in v))
                for k, v in dupes.items()))

    def test_every_rail_icon_exists_in_the_sidebar_icon_set(self):
        """The rail's icons are a FIXED inline Lucide set in pb_sidebar.js; an
        unknown name renders a plain circle, silently. This is the only thing
        that catches a typo before a user sees a row of identical dots."""
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

        items = self.env['pb.sidebar.item'].with_context(active_test=False).search([])
        missing = sorted({i.icon for i in items if i.icon and i.icon not in known})
        self.assertFalse(
            missing,
            'sidebar icons with no path in the fixed set (they render as plain '
            'circles): %s' % missing)
