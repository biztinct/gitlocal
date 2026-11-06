# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P4 — T1: the Close tolerance resolves company-else-global.

Two things are proved here and nowhere else:

  1. `_variance_for_company` follows the SAME two-search rule as
     `_grace_for_company` — a company row beats the global row, and never the
     other way round. This is C18.20's trap: a single `order='company_id desc'`
     search returns the NULL/global row FIRST, so the override silently never
     applies and the surface looks merely "mis-configured";
  2. the DEFAULTS actually landed in the database. W13.1 exists because a
     repo-only fix is indistinguishable from a real one unless something reads
     the database back — and this module's rule row is `noupdate="1"`, i.e.
     exactly the shape that silently ignores a data-file change.
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCloseTolerance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Rule = cls.env['pb.attendance.rule'].sudo()
        cls.company = cls.env.company
        cls.other = cls.env['res.company'].create({'name': 'P4 Tolerance Co'})

    # ------------------------------------------------------------------ T1
    def test_the_migration_seeded_the_global_row(self):
        """Read it back from the DATABASE, not from the field default.

        The global rule ships in a `noupdate="1"` file, so the two new fields
        could only arrive through migrations/19.0.1.0.7/pre-migrate.py (or, on a
        fresh install, through the data file itself). Either way the row must
        answer 10 / 0.5 — a 0 here would mean "every second counts", which is
        not a default anybody chose.
        """
        row = self.env.ref('pb_attendance_flow.attendance_rule_global',
                           raise_if_not_found=False)
        if not row:
            self.skipTest('the global attendance rule is not installed here')
        self.env.cr.execute(
            "SELECT variance_minutes, variance_hours_week "
            "FROM pb_attendance_rule WHERE id = %s", (row.id,))
        minutes, hours = self.env.cr.fetchone()
        self.assertEqual(minutes, 10)
        self.assertAlmostEqual(hours, 0.5, places=6)

    def test_the_field_defaults_match_the_seeded_values(self):
        """A new row created by an admin must agree with the migrated one, or
        the two paths into the same policy disagree from day one."""
        rule = self.Rule.new({'name': 'x'})
        self.assertEqual(rule.variance_minutes, 10)
        self.assertAlmostEqual(rule.variance_hours_week, 0.5, places=6)

    def test_a_company_rule_beats_the_global_one(self):
        """C18.20: two searches, never one ordered search."""
        self.Rule.search([]).write({'active': False})
        self.Rule.create({
            'name': 'P4 global', 'company_id': False,
            'variance_minutes': 10, 'variance_hours_week': 0.5})
        self.Rule.create({
            'name': 'P4 company', 'company_id': self.company.id,
            'variance_minutes': 3, 'variance_hours_week': 0.25})

        self.assertEqual(
            self.Rule._variance_for_company(self.company), (3, 0.25))
        # a company with no rule of its own still gets the global one
        self.assertEqual(
            self.Rule._variance_for_company(self.other), (10, 0.5))

    def test_no_rule_at_all_falls_back_to_the_p4_defaults(self):
        """The module must behave identically to the pre-P4 hardcode when the
        config table is empty — the `_grace_for_company` posture."""
        self.Rule.search([]).write({'active': False})
        self.assertEqual(
            self.Rule._variance_for_company(self.company), (10, 0.5))

    def test_a_stored_zero_is_respected_not_replaced(self):
        """0 is a legitimate policy ("the plan is the plan"). Only the ABSENCE
        of a rule may fall back, or an admin who tightens to zero would silently
        get 10 minutes of slack back."""
        self.Rule.search([]).write({'active': False})
        self.Rule.create({
            'name': 'P4 exact', 'company_id': self.company.id,
            'variance_minutes': 0, 'variance_hours_week': 0.0})
        self.assertEqual(
            self.Rule._variance_for_company(self.company), (0, 0.0))

    def test_the_bounds_are_enforced_in_postgres(self):
        """W33: `models.Constraint`, so the CHECK really exists in the database
        rather than being a warning Odoo 19 logged once and ignored."""
        self.env.cr.execute(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = 'pb_attendance_rule'::regclass "
            "AND conname LIKE '%%variance%%'")
        names = {r[0] for r in self.env.cr.fetchall()}
        self.assertTrue(names, 'no variance CHECK constraint reached PostgreSQL')

        self.Rule.search([]).write({'active': False})
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.Rule.create({'name': 'bad', 'company_id': False,
                                  'variance_minutes': -1})
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.Rule.create({'name': 'bad2', 'company_id': False,
                                  'variance_hours_week': 999.0})

    def test_grace_and_tolerance_stay_independent(self):
        """They answer different questions (see the model docstring) — writing
        one must never move the other."""
        self.Rule.search([]).write({'active': False})
        rule = self.Rule.create({
            'name': 'P4 split', 'company_id': self.company.id,
            'grace_in_minutes': 15, 'grace_out_minutes': 15,
            'open_checkout_hours': 16,
            'variance_minutes': 10, 'variance_hours_week': 0.5})
        rule.variance_minutes = 25
        self.assertEqual(
            self.Rule._grace_for_company(self.company), (15, 15, 16))
        self.assertEqual(
            self.Rule._variance_for_company(self.company), (25, 0.5))

    def test_the_single_active_rule_per_scope_guard_still_holds(self):
        """Regression: the P4 fields must not have disturbed the Phase-G
        one-active-rule-per-scope constraint."""
        self.Rule.search([]).write({'active': False})
        self.Rule.create({'name': 'a', 'company_id': self.company.id})
        with self.assertRaises(ValidationError):
            self.Rule.create({'name': 'b', 'company_id': self.company.id})
