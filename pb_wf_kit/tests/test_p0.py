# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P0 — data assertions for WP-H (sidebar hygiene).

pb_wf_kit itself has no models; it hosts these because it is the one module the
whole Workforce program depends on, so the assertions run wherever the redesign
is installed without adding a tests/ package to five unrelated modules.

Every test skip-guards on the records actually being present: pb_wf_kit installs
standalone (its only hard deps are web / pb_theme / pb_import_kit), and a bare
install must not fail because pb_sidebar or a cockpit module is absent.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWorkforceP0Sidebar(TransactionCase):

    def _section(self):
        if 'pb.sidebar.item' not in self.env:
            self.skipTest('pb_sidebar is not installed')
        sec = self.env.ref('pb_sidebar.sec_workforce', raise_if_not_found=False)
        if not sec:
            self.skipTest('the Workforce sidebar section is not installed')
        return sec

    def _items(self):
        sec = self._section()
        # with_context(active_test=False): a deactivated item still occupies its
        # sequence the moment someone re-enables it, so uniqueness must hold for
        # the whole set, not just the visible one.
        return self.env['pb.sidebar.item'].with_context(active_test=False).search(
            [('section_id', '=', sec.id)])

    # -------------------------------------------------------------- WP-H (1/2)
    def test_workforce_sequences_are_unique(self):
        """No two Workforce items share a sequence (W8).

        Two collisions existed before P0 — Leave vs Timecards on 30, and
        Business Trips vs Overtime Desk on 37 — which left the rail order up to
        whatever the database returned.
        """
        items = self._items()
        if len(items) < 2:
            self.skipTest('not enough Workforce sidebar items to compare')
        seqs = items.mapped('sequence')
        dupes = sorted({s for s in seqs if seqs.count(s) > 1})
        self.assertFalse(
            dupes,
            'Workforce sidebar sequences must be unique; duplicated: %s (%s)' % (
                dupes,
                ', '.join('%s=%s' % (i.name, i.sequence)
                          for i in items.sorted('sequence') if i.sequence in dupes),
            ),
        )

    def test_moved_items_landed_on_their_new_sequences(self):
        """The two de-collided records really moved.

        This is the guard for W13: both records live in data files whose
        `noupdate` flag decides whether an upgrade applies them at all, and one
        of those files was noupdate="1" until P0. Asserting the value in the DB
        is the only way to catch a repo-only "fix".
        """
        # P0 moved these off their collisions (32 / 38 / 37); P1b renumbered the
        # whole section to the Option-A rail (40 / 50 / 60); P3a folded that rail
        # into Mission Control and parked all seven items in the 900 band, so the
        # CURRENT truth is below.
        # The test still does exactly its job — it is the W13/W13.1 guard proving
        # each record's declaring data file can actually reach it — and
        # pb_business_trip is the interesting one twice over: frozen until P0
        # for pb_timeoff, frozen until P1b for itself. Updating the expectation
        # with the change is deliberate: a red gate nobody believes is the same
        # as no gate.
        expected = {
            'pb_timeoff.item_leave_center': 909,
            'pb_hr_workforce.item_wf_ot_desk': 910,
            'pb_business_trip.item_wf_trips': 911,
        }
        checked = 0
        for xmlid, seq in expected.items():
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            if not rec:
                continue
            checked += 1
            self.assertEqual(
                rec.sequence, seq,
                '%s should sit at sequence %s, found %s — if the repo says %s, '
                'the declaring data file is probably still noupdate="1" (W13)'
                % (xmlid, seq, rec.sequence, seq))
        if not checked:
            self.skipTest('no Workforce cockpit modules installed')

    # -------------------------------------------------------------- WP-H (2/2)
    def test_payroll_report_item_carries_the_payroll_gate(self):
        """The Payroll Report rail entry must be gated like its menu twin.

        pb_hr_workforce/views/menu_views.xml declares the legacy menu with
        groups="om_hr_payroll.group_hr_payroll_user"; the sidebar item shipped
        ungated, exposing a salary-aggregate dashboard to every Workforce
        persona. W8 requires the two gates to match.
        """
        item = self.env.ref('pb_sidebar.item_wf_payroll_report', raise_if_not_found=False)
        if not item:
            self.skipTest('the Payroll Report sidebar item is not installed')
        group = self.env.ref('om_hr_payroll.group_hr_payroll_user', raise_if_not_found=False)
        if not group:
            self.skipTest('om_hr_payroll is not installed')
        self.assertIn(
            group.id, item.groups_id.ids,
            'item_wf_payroll_report must require om_hr_payroll.group_hr_payroll_user, '
            'matching menu_payroll_report')
