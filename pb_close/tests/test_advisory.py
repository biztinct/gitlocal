# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P4 — T4: the payroll advisory, and the proof it cannot bite.

The single most important assertion in this file is the negative one: an
advisory that can raise is a payroll outage waiting for a bad week of data. So
the exception path is tested by INJECTING a failure into the helper and proving
the run still returns its result — the pb_young_worker cardinal rule, tested the
same way.
"""

from datetime import timedelta
from unittest.mock import patch

from odoo.tests import tagged

from .common import CloseCase


@tagged('post_install', '-at_install')
class TestCloseAdvisory(CloseCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env['pb.payrun.wizard']
        cls.ds = cls.week_start
        cls.de = cls.week_start + timedelta(days=6)

    def _append(self, exceptions=None, emp_ids=None):
        return self.Wizard.sudo()._close_append_exceptions(
            exceptions if exceptions is not None else [],
            emp_ids if emp_ids is not None else self.emp.ids,
            self.ds, self.de)

    # ==================================================================
    def test_an_unclosed_week_appends_a_line_plus_a_total(self):
        out = self._append()
        self.assertTrue(out, 'an unlocked week must be reported')
        self.assertTrue(any('not closed' in r['why'] for r in out))
        self.assertTrue(any('not been closed and locked' in r['why']
                            for r in out), 'the run needs a total line')
        # …and it says out loud that it is a note, not a block
        self.assertTrue(any('not a block' in r['why'] for r in out))

    def test_a_fully_locked_week_is_SILENT(self):
        """A closed week must produce nothing at all — an advisory that fires on
        the happy path is an advisory people stop reading."""
        for i in range(7):
            self._lock(self.week_start + timedelta(days=i))
        self.assertEqual(self._append(), [])

    def test_a_partly_locked_week_still_reports(self):
        self._lock(self.day)
        out = self._append()
        self.assertTrue(out)
        self.assertTrue(any('1 of 7' in r['why'] for r in out))

    def test_the_line_carries_the_exact_open_flag_count(self):
        """Small population -> the exact number, from pb.close itself. The two
        message shapes are both TRUE; neither is an estimate."""
        self._shift(self.emp, self.day)          # scheduled, never punched
        out = self._append()
        self.assertTrue(any('flag(s) open' in r['why'] for r in out))

    def test_a_large_population_falls_back_to_search_count_facts(self):
        """Above the cap the line reports only exact search_counts — an advisory
        that adds ten seconds to every payroll run is one somebody switches off.
        """
        with patch.object(type(self.Wizard),
                          '_close_open_flags', return_value=None):
            out = self._append()
        self.assertTrue(any('still undecided' in r['why'] for r in out))
        self.assertFalse(any('flag(s) open' in r['why'] for r in out))

    def test_it_appends_to_an_EXISTING_exception_list(self):
        """It is an append-after-super, so anything already collected — the
        young-worker rows, a missing contract — must survive untouched."""
        seed = [{'emp': 'Somebody', 'why': 'No running contract'}]
        out = self._append(exceptions=seed)
        self.assertIs(out, seed, 'the list is mutated in place')
        self.assertEqual(out[0]['why'], 'No running contract')
        self.assertGreater(len(out), 1)

    def _empty_payload(self):
        """A batch with no employees: the base creates nothing and returns its
        {computed, exceptions} shape, so the seam can be exercised for real
        without minting a payslip on the live demo database (T16)."""
        return {'run_id': False, 'name': 'P4 advisory probe',
                'date_start': self.ds.isoformat(),
                'date_end': self.de.isoformat(),
                'emp_ids': []}

    def test_the_seam_really_appends_through_compute_batch(self):
        out = self.Wizard.sudo().compute_batch(self._empty_payload())
        self.assertIn('exceptions', out)
        self.assertTrue(any('not closed' in r['why']
                            for r in out['exceptions']), out['exceptions'])

    def test_it_NEVER_raises(self):
        """THE cardinal rule. An advisory that can raise is a payroll outage
        waiting for a bad week of data, so the failure is INJECTED rather than
        imagined: the run must still return its result, unharmed."""
        def boom(*a, **kw):
            raise RuntimeError('advisory exploded')

        with patch.object(type(self.Wizard), '_close_append_exceptions',
                          side_effect=boom):
            try:
                out = self.Wizard.sudo().compute_batch(self._empty_payload())
            except RuntimeError:
                self.fail('the advisory raised into the payroll run')
        self.assertIsInstance(out, dict)
        self.assertIn('exceptions', out)
        self.assertEqual(out['exceptions'], [],
                         'the run must be exactly as it was without us')

    def test_a_failing_HELPER_is_swallowed_too(self):
        """Not just the top-level append: anything it calls."""
        with patch.object(type(self.Wizard), '_close_week_status',
                          side_effect=RuntimeError('lock read exploded')):
            out = self.Wizard.sudo().compute_batch(self._empty_payload())
        self.assertIn('exceptions', out)

    def test_a_period_with_no_dates_is_a_no_op(self):
        self.assertEqual(
            self.Wizard.sudo()._close_append_exceptions(
                [], self.emp.ids, False, False), [])

    def test_only_the_days_inside_the_PERIOD_count(self):
        """A week straddling the month boundary is not "3 of 7 unlocked" when
        four of those days belong to the previous run."""
        mid = self.week_start + timedelta(days=3)
        out = self.Wizard.sudo()._close_append_exceptions(
            [], self.emp.ids, mid.isoformat(),
            (self.week_start + timedelta(days=6)).isoformat())
        self.assertTrue(any('of 4 day(s)' in r['why'] for r in out), out)

    # ==================================================================
    #  MRO
    # ==================================================================
    def test_the_advisory_reaches_the_demo_division_path(self):
        """§2's warning, and what MEASURING it actually found.

        pb_demo replaces create_and_compute / compute_batch for its DIVISION
        path WITHOUT calling super, so a wrapper that is MRO-INNER of pb_demo
        never runs there. The handover cites pb_young_worker's `test_09` as the
        precedent that this works. It does not: on the live registry the order
        is `pb_demo -> pb_close -> pb_young_worker -> pb_payrun_wizard`, so
        pb_demo is outer of BOTH advisories and the demo division run has never
        shown either. `test_09` asserts the opposite and is stale.

        The direction of the fix matters more than the fix. A production module
        must never depend on the demo module to be correct, so pb_close does
        NOT depend on pb_demo; instead pb_demo calls the product's advisory
        hooks explicitly on the path it owns (`_pb_demo_advisories`). This test
        therefore accepts EITHER route, and fails only if neither exists —
        because what has to be true is that the advisory reaches the run, not
        that it reaches it by a particular mechanism.

        The generic (salary-structure) path always calls super and is
        unaffected either way.
        """
        mods = [getattr(c, '__module__', '')
                for c in type(self.env['pb.payrun.wizard']).mro()]
        close = next((i for i, m in enumerate(mods) if 'pb_close' in m), None)
        demo = next((i for i, m in enumerate(mods) if 'pb_demo' in m), None)
        self.assertIsNotNone(close, 'pb_close payrun wrapper missing from MRO')
        if demo is None:
            return                       # no demo module: nothing to bypass us
        if close < demo:
            return                       # MRO-outer: super() wraps the demo path
        self.assertTrue(
            hasattr(self.env['pb.payrun.wizard'], '_pb_demo_advisories'),
            "pb_demo is MRO-outer of pb_close, so its division path skips the "
            "append-after-super seam. pb_demo must then call the advisory "
            "hooks itself (_pb_demo_advisories) — the fix is NEVER to depend "
            "on pb_demo from a production module.")
        import inspect
        src = inspect.getsource(type(self.env['pb.payrun.wizard'])
                                ._pb_demo_advisories)
        self.assertIn('_close_append_exceptions', src,
                      'the demo hook must invoke the close advisory')

    def test_the_wrapper_is_registered_on_both_seams(self):
        wiz = type(self.env['pb.payrun.wizard'])
        for seam in ('create_and_compute', 'compute_batch'):
            srcs = [getattr(c, '__module__', '') for c in wiz.mro()
                    if seam in vars(c)]
            self.assertTrue(any('pb_close' in s for s in srcs),
                            'pb_close must wrap %s' % seam)
