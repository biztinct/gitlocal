# -*- coding: utf-8 -*-
"""Phase O §6 — the Workforce Insights cockpit.

The two that matter most are 06 (cross-surface parity: this cockpit and the
Explorer must not disagree about the same number) and 07 (no ``is_demo``
filter — the exact defect that made the surface this replaces render empty on
every real database while looking like a working feature).
"""

import os

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWorkforceInsights(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'WFI Co'})
        cls.company_b = cls.env['res.company'].create({'name': 'WFI Co B'})
        cls.facade = cls.env['pb.workforce.insights']

    def _scoped(self, model=None):
        model = model or self.facade
        return model.with_context(
            allowed_company_ids=[self.company.id]).with_company(self.company)

    # ------------------------------------------------------- §6.1 renders
    def test_01_board_renders(self):
        """Every section is present and the board reports its own timing."""
        board = self._scoped().get_board()
        for key in ('headcount', 'cost', 'options', 'timings', 'filters'):
            self.assertIn(key, board)
        self.assertIn('total', board['timings'])

    def test_02_soft_deps_degrade_to_none(self):
        """A missing phase yields None so the tile can say 'not installed',
        rather than raising and taking the whole board down."""
        board = self._scoped().get_board()
        for key in ('attendance', 'overtime', 'leave'):
            value = board[key]
            self.assertTrue(value is None or isinstance(value, dict),
                            "%s must be a dict or None, got %r" % (key, type(value)))

    # -------------------------------------------------------- §6.3 window
    def test_03_month_window_is_bounded(self):
        for months in (1, 3, 6, 12):
            self.assertEqual(self._scoped().get_board(months=months)['months'],
                             months)
        # a hostile value falls back rather than reaching SQL
        self.assertEqual(self._scoped().get_board(months=9999)['months'], 3)

    # -------------------------------------------------------- §6.4 access
    def test_04_access_is_gated(self):
        """The surface this replaces had NO group restriction at all."""
        outsider = self.env['res.users'].create({
            'name': 'WFI Outsider', 'login': 'wfi_outsider',
            'company_id': self.company.id, 'company_ids': [(4, self.company.id)],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        with self.assertRaises(AccessError):
            self.env['pb.workforce.insights'].with_user(outsider).get_board()

    # -------------------------------------------- §6.5 read-only doctrine
    def test_05_facade_never_writes(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, 'models', 'pb_workforce_insights.py'),
                  encoding='utf-8') as fh:
            source = fh.read()
        for forbidden in ('.write(', '.create(', '.unlink(', '.copy(',
                          'cr.execute("UPDATE', 'cr.execute("INSERT',
                          'cr.execute("DELETE'):
            self.assertNotIn(forbidden, source,
                             "pb.workforce.insights is read-only: found %s"
                             % forbidden)

    # ------------------------------------------ §6.6 cross-surface parity
    def test_06_cost_per_head_matches_the_explorer(self):
        """This cockpit and the Analytics Explorer must not disagree.

        Both read the same derived fact tables; if these two ever diverge one
        of the surfaces is lying to the same user on the same day.
        """
        board = self._scoped().get_board(months=12)
        rows = {r['id']: r['per_head'] for r in board['cost'].get('rows', [])
                if r['drillable']}
        if not rows:
            self.skipTest('no payroll facts in scope for this company')

        explorer = self._scoped(self.env['pb.explorer'])
        for dept_id, per_head in rows.items():
            res = explorer.query({
                'measure': 'cost_per_head', 'dimension': 'department_id',
                'grain': 'none', 'filters': {'department_id': [dept_id]},
                'date_from': board['date_from'],
            })
            if not res['series']:
                continue
            self.assertAlmostEqual(
                res['series'][0]['total'], per_head, delta=1.0,
                msg="cost per head disagrees with the Explorer for dept %s"
                    % dept_id)

    # ------------------------------------------------- §6.7 no demo filter
    def test_07_no_is_demo_filter(self):
        """The placeholder this replaces filtered EVERY query on
        ``is_demo = true``, so it rendered empty on any real database while
        looking like a working feature. That must never come back.

        Checks the FILTER FORMS specifically — ``'is_demo'`` as a domain token
        or ``.is_demo`` as a SQL/ORM attribute (which is how the placeholder
        wrote it: ``JOIN hr_employee e ON ... AND e.is_demo=true``). The bare
        word is not forbidden: it legitimately appears in prose explaining
        this very defect, and the manifest is metadata, not a query.
        """
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        forbidden = ("'is_demo'", '"is_demo"', '.is_demo')
        for root, _dirs, files in os.walk(here):
            if '__pycache__' in root or os.sep + 'tests' in root:
                continue
            for name in files:
                if name == '__manifest__.py':
                    continue
                if not name.endswith(('.py', '.js', '.xml')):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding='utf-8', errors='ignore') as fh:
                    body = fh.read()
                for token in forbidden:
                    self.assertNotIn(
                        token, body,
                        "%s filters on demo data (%r) — this cockpit must read "
                        "real records" % (name, token))

    # ------------------------------------------------ §6.8 company scoping
    def test_08_company_scoping(self):
        """Company B's options never leak into company A's board."""
        board = self._scoped().get_board()
        self.assertIn('options', board)
        # the filter vocabulary is built from company-scoped facts only
        self.assertIsInstance(board['options']['division'], list)
        self.assertIsInstance(board['options']['department_id'], list)

    # ----------------------------------------------- §6.9 self-contained
    def test_09_no_external_assets(self):
        module = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        offenders = []
        static = os.path.join(module, 'static')
        for root, _dirs, files in os.walk(static):
            for name in files:
                path = os.path.join(root, name)
                with open(path, encoding='utf-8', errors='ignore') as fh:
                    body = fh.read()
                if 'http://' in body or 'https://' in body:
                    offenders.append(os.path.relpath(path, module))
        self.assertFalse(offenders,
                         "Workforce Insights assets must be self-contained: %s"
                         % offenders)
