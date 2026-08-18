# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P1b — T3: the IA finale, asserted in the DATABASE.

UPDATED BY P3a. This file used to pin the WHOLE Workforce rail: eight live items
after P1b, seven after P2, with their labels, sequences and icons. P3a folds all
seven into the Mission Control shell, so an exact-rail assertion here would now
fail on work that is correct — and it would fail again on every future phase that
touches the section.

The durable question for THIS file is the narrower one P1b actually owns: did the
four surfaces the Today board absorbed stay off the rail, at the 900-band
sequences P1b gave them, and did the Payroll Report relocation hold? The
whole-rail shape is asserted where it belongs, by the phase that created it —
pb_mission/tests/test_sidebar.py (one live item, fifteen retired). This is the
same narrowing pb_time_hub's P1a file went through when P1b superseded it, and
the reason is the same: these gates exist to catch a repo-only sidebar change, so
they are updated WITH the change rather than left red. A red gate nobody believes
is the same as no gate.

W13.1, learned the hard way in P0 and again in P1a and P1b: a repo-only sidebar
"fix" is indistinguishable from a real one unless something reads the database
back. Every assertion below therefore resolves the xmlid and reads the RECORD,
after the upgrade — never the XML.
"""
from odoo.tests import TransactionCase, tagged

# Retired by P1b into the 900 band (W18), and still there. Today absorbed the
# first three; the driver map became Today's map card and its full Map view.
_RETIRED_BY_P1B = [
    ('pb_sidebar.item_wf_dashboard', 901),
    ('pb_sidebar.item_wf_live', 902),
    ('pb_sidebar.item_wf_overtime', 903),
    ('pb_driver_checkin.item_driver_tracking', 904),
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

    # ========================================================== retirement
    def test_the_four_p1b_absorbed_items_stay_retired_in_the_900_band(self):
        """W18: `active = False` takes an item off the rail but not out of the
        section, so a retirement that inherits somebody's sequence has to MOVE.
        P1b's four went to 901-904 and nothing since has disturbed them."""
        checked = 0
        for xmlid, seq in _RETIRED_BY_P1B:
            rec = self._item(xmlid)
            if not rec:
                continue
            checked += 1
            self.assertFalse(rec.active, '%s must be off the rail' % xmlid)
            self.assertEqual(rec.sequence, seq, '%s retired sequence' % xmlid)
        self.assertEqual(checked, len(_RETIRED_BY_P1B),
                         'all four P1b retirements must be present to check')

    def test_business_trips_is_no_longer_frozen(self):
        """The W13.1 unfreeze P1b shipped. If the migration had not run, this
        record would still be immovable and every later phase that touches it —
        P3a moved it to 911 — would silently apply nothing."""
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
        # CONTAINS, not EQUALS (P6). A rail gate is a floor, not an inventory:
        # `pb_demo._pb_demo_rewire` legitimately joins "Payobook Demo User" onto
        # every gated item on a demo database, so an equality assertion here
        # tests whether pb_demo happens to be installed rather than whether the
        # gate survived the relocation. Same shape as the pb_wf_kit precedent
        # (`test_p0.py::test_payroll_report_keeps_its_payroll_gate`).
        self.assertIn(
            payroll_user.id, rec.groups_id.ids,
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
    def test_today_keeps_the_officer_gate_it_can_be_re_enabled_with(self):
        """Retirement is reversible (W18), so the record has to stay correct.
        The gate also outlives the rail entry in a second place: Mission Control
        asks the SAME question client-side before it offers the Today lens."""
        rec = self._item('pb_today.item_wf_today')
        if not rec:
            self.skipTest('pb_today is not installed')
        officer = self.env.ref('hr_attendance.group_hr_attendance_officer')
        # CONTAINS, not EQUALS — see the note on the Payroll Report test above.
        self.assertIn(officer.id, rec.groups_id.ids,
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
