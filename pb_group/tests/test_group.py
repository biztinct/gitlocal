# -*- coding: utf-8 -*-
"""GROUP P1 — the behaviour this module promises.

T1  the three rate policies pick the rate they say they pick
T2  an unpriced pair is refused, the same currency is trivial, rounding is the
    target currency's
T3  a rate row owned by the head office is visible to a subsidiary in the same
    group, and a row owned by a company outside it is not (gotcha GR2)
T4  the budget shim still answers a two-tuple with the budget's own rounding
T5  a company belongs to one group only; moving and archiving both behave
T6  one department, one division, on any given day
T7  a division attached at the top of a branch covers everything under it
T8  the suggestions are one per distinct top-level name, merged across
    companies, and skip what is already attached
T9  the screen's headcounts equal a direct count of the roster, quickly
T10 a reader may look and may not change
T13 the demo module's own company field still works exactly as it did
T14 `res.company.parent_id` is never written by this module
"""

import os
import re
import time
from datetime import date, timedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, new_test_user, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@tagged('post_install', '-at_install')
class TestPbFx(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fx = cls.env['pb.fx']
        Currency = cls.env['res.currency'].sudo()
        cls.a = Currency.create({'name': 'ZQA', 'symbol': 'a',
                                 'decimal_places': 2})
        cls.b = Currency.create({'name': 'ZQB', 'symbol': 'b',
                                 'decimal_places': 0})
        cls.c = Currency.create({'name': 'ZQC', 'symbol': 'c'})
        cls.company = cls.env.company
        Rate = cls.env['res.currency.rate'].sudo()
        cls.rates = Rate.create([
            {'currency_id': cls.a.id, 'name': '2026-01-10', 'rate': 2.0,
             'company_id': cls.company.id},
            {'currency_id': cls.a.id, 'name': '2026-01-25', 'rate': 4.0,
             'company_id': cls.company.id},
            {'currency_id': cls.b.id, 'name': '2026-01-05', 'rate': 1.0,
             'company_id': cls.company.id},
        ])

    # ------------------------------------------------------------------ T1
    def test_t1_each_policy_picks_the_rate_it_says_it_does(self):
        """T1. Three policies, three different answers on the same month."""
        month_end = self.fx.rate(self.a, self.b, date(2026, 1, 15),
                                 policy='month_end')
        self.assertTrue(month_end['known'])
        # the last ZQA row on or before 31 January is 4.0
        self.assertAlmostEqual(month_end['rate'], 1.0 / 4.0, places=9)
        self.assertEqual(month_end['rate_date'], '2026-01-25')

        payment = self.fx.rate(self.a, self.b, date(2026, 1, 15),
                               policy='payment_date')
        self.assertTrue(payment['known'])
        self.assertAlmostEqual(payment['rate'], 1.0 / 2.0, places=9)
        self.assertEqual(payment['rate_date'], '2026-01-10')

        average = self.fx.rate(self.a, self.b, date(2026, 1, 15),
                               policy='month_avg')
        self.assertTrue(average['known'])
        self.assertAlmostEqual(average['rate'], 1.0 / 3.0, places=9)

        empty = self.fx.rate(self.a, self.b, date(2026, 2, 15),
                             policy='month_avg')
        self.assertFalse(empty['known'],
                         'a month with no rate rows cannot be averaged')
        self.assertIn('ZQA', empty['note'])

    # ------------------------------------------------------------------ T2
    def test_t2_it_refuses_what_it_does_not_know_and_rounds_to_the_target(self):
        """T2. No implicit one-for-one, and the target's own decimals."""
        unknown = self.fx.rate(self.c, self.a, date(2026, 1, 15))
        self.assertFalse(unknown['known'],
                         'ZQC has no rate row, so nothing can be said')
        value, known, meta = self.fx.convert(1000, self.c, self.a,
                                             date(2026, 1, 15))
        self.assertFalse(known)
        self.assertEqual(value, 0.0)
        self.assertTrue(meta['note'])

        same = self.fx.rate(self.a, self.a, date(2026, 1, 15))
        self.assertTrue(same['known'])
        self.assertEqual(same['rate'], 1.0)

        # ZQB has 0 decimal places, so a converted figure comes back whole.
        value, known, _meta = self.fx.convert(
            1000, self.a, self.b, date(2026, 1, 15), policy='payment_date')
        self.assertTrue(known)
        self.assertEqual(value, 500)
        self.assertEqual(value, round(value))

        # And the caller may ask for a different rounding, which is what the
        # budget screen does to keep its stored numbers the shape they were.
        value, known, _meta = self.fx.convert(
            1001, self.a, self.b, date(2026, 1, 15), policy='payment_date',
            decimals=2)
        self.assertEqual(value, 500.5)

        # A typed rate is the row's own answer and always wins.
        value, known, meta = self.fx.convert(1000, self.c, self.a,
                                             manual_rate=2.5)
        self.assertTrue(known)
        self.assertEqual(value, 2500.0)
        self.assertEqual(meta['policy'], 'manual')

    # ------------------------------------------------------------------ T3
    def test_t3_a_group_sees_the_head_offices_rate_rows(self):
        """T3. Gotcha GR2, in one test."""
        Company = self.env['res.company'].sudo()
        head = Company.create({'name': 'ZQ Head office'})
        arm = Company.create({'name': 'ZQ Subsidiary'})
        outside = Company.create({'name': 'ZQ Somebody else'})
        group = self.env['pb.group'].sudo().create({
            'name': 'ZQ Group',
            'presentation_currency_id': self.a.id,
        })
        (head + arm).write({'pb_group_id': group.id})

        Rate = self.env['res.currency.rate'].sudo()
        Rate.create([
            {'currency_id': self.a.id, 'name': '2026-03-01', 'rate': 5.0,
             'company_id': head.id},
            {'currency_id': self.b.id, 'name': '2026-03-01', 'rate': 1.0,
             'company_id': head.id},
        ])
        found = self.fx.rate(self.a, self.b, date(2026, 3, 15), company=arm,
                             policy='month_end')
        self.assertTrue(found['known'],
                        'the head office prices the money the whole group '
                        'spends')
        self.assertAlmostEqual(found['rate'], 1.0 / 5.0, places=9)

        Rate.create([
            {'currency_id': self.c.id, 'name': '2026-03-01', 'rate': 9.0,
             'company_id': outside.id},
        ])
        stranger = self.fx.rate(self.c, self.b, date(2026, 3, 15), company=arm,
                                policy='month_end')
        self.assertFalse(stranger['known'],
                         'a rate owned by a company outside the group is not '
                         'this group\'s to use')
        self.assertNotIn(outside.id, self.fx.rate_companies(arm))
        self.assertIn(head.id, self.fx.rate_companies(arm))

    # ------------------------------------------------------------------ T4
    def test_t4_the_budget_shim_keeps_its_own_shape(self):
        """T4. The rest of T4 is `pb_budget`'s own suite, run unchanged."""
        fx = self.env['pb.budget.fx']
        answer = fx.convert(1000, self.a, self.b, date(2026, 1, 15))
        self.assertIsInstance(answer, tuple)
        self.assertEqual(len(answer), 2)
        value, known = answer
        self.assertTrue(known)
        # The budget rounds to two places whatever the target currency says.
        self.assertEqual(value, 500.0)
        self.assertTrue(fx.presentation_currency())
        self.assertFalse(fx.rate_known(self.c, self.a, date(2026, 1, 15)))
        self.assertTrue(fx.unknown_rate_note(self.c, self.a))


@tagged('post_install', '-at_install')
class TestPbGroup(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company'].sudo()
        cls.one = Company.create({'name': 'ZQ One'})
        cls.two = Company.create({'name': 'ZQ Two'})
        cls.group = cls.env['pb.group'].sudo().create({
            'name': 'ZQ First group',
            'presentation_currency_id': cls.env.company.currency_id.id,
        })
        cls.other = cls.env['pb.group'].sudo().create({
            'name': 'ZQ Second group',
            'presentation_currency_id': cls.env.company.currency_id.id,
        })
        cls.room = cls.env['pb.group.room']

    # ------------------------------------------------------------------ T5
    def test_t5_a_company_is_in_one_group_at_a_time(self):
        """T5. Moving a company between groups updates both ends."""
        self.room.set_members(self.group.id, [self.one.id, self.two.id])
        self.assertEqual(set(self.group.company_ids.ids),
                         {self.one.id, self.two.id})

        self.room.set_members(self.other.id, [self.two.id])
        self.assertEqual(self.two.pb_group_id, self.other)
        self.assertEqual(self.group.company_ids.ids, [self.one.id])

        self.group.write({'active': False})
        self.assertFalse(self.one.pb_group_id,
                         'a group that is put away lets its companies go')

    def test_the_branch_tree_is_never_touched(self):
        """Ruling G1, checked against behaviour and not only against a grep."""
        before = {c.id: c.parent_id.id
                  for c in self.env['res.company'].sudo().search([])}
        self.room.set_members(self.group.id, [self.one.id, self.two.id])
        after = {c.id: c.parent_id.id
                 for c in self.env['res.company'].sudo().search([])}
        self.assertEqual(before, after)

    # ------------------------------------------------------------------ T6
    def test_t6_one_department_one_division_at_a_time(self):
        """T6. The refusal is a sentence a person can act on."""
        Department = self.env['hr.department'].sudo()
        Link = self.env['pb.division.link'].sudo()
        Division = self.env['pb.division'].sudo()
        retail = Division.create({'name': 'ZQ Retail'})
        trade = Division.create({'name': 'ZQ Trade'})
        shop = Department.create({'name': 'ZQ Shops',
                                  'company_id': self.one.id})
        Link.create({'division_id': retail.id, 'department_id': shop.id,
                     'date_from': '2026-01-01'})
        with self.assertRaises(ValidationError) as caught:
            Link.create({'division_id': trade.id, 'department_id': shop.id,
                         'date_from': '2026-06-01'})
        message = str(caught.exception)
        self.assertIn('ZQ Retail', message)
        self.assertIn('ZQ Shops', message)

        # Sequential is fine: a history is a history.
        Link.search([('department_id', '=', shop.id)]).write(
            {'date_to': '2026-05-31'})
        later = Link.create({'division_id': trade.id, 'department_id': shop.id,
                             'date_from': '2026-06-01'})
        self.assertTrue(later.id)
        self.assertEqual(later.company_id, self.one)

    # ------------------------------------------------------------------ T7
    def test_t7_an_attachment_at_the_top_covers_the_branch(self):
        """T7. Attach Retail once; Groceries and Bread come with it."""
        Department = self.env['hr.department'].sudo()
        Division = self.env['pb.division'].sudo()
        retail = Division.create({'name': 'ZQ Retail branch'})
        top = Department.create({'name': 'ZQ Retail',
                                 'company_id': self.one.id})
        mid = Department.create({'name': 'ZQ Groceries',
                                 'company_id': self.one.id,
                                 'parent_id': top.id})
        leaf = Department.create({'name': 'ZQ Bread', 'company_id': self.one.id,
                                  'parent_id': mid.id})
        self.env['pb.division.link'].sudo().create({
            'division_id': retail.id, 'department_id': top.id})
        self.assertEqual(Division.division_for(leaf), retail)
        self.assertEqual(Division.division_for(mid), retail)

        loose = Department.create({'name': 'ZQ Nowhere',
                                   'company_id': self.one.id})
        self.assertFalse(Division.division_for(loose))

    # ------------------------------------------------------------------ T8
    def test_t8_the_suggestions_merge_the_same_name_across_companies(self):
        """T8. One suggestion per distinct top-level name, accents folded."""
        Department = self.env['hr.department'].sudo()
        Department.create([
            {'name': 'ZQ Retail', 'company_id': self.one.id},
            {'name': 'ZQ RETAIL', 'company_id': self.two.id},
            {'name': 'ZQ Logistics', 'company_id': self.one.id},
        ])
        Department.create({'name': 'ZQ Under retail',
                           'company_id': self.one.id,
                           'parent_id': Department.search(
                               [('name', '=', 'ZQ Retail')], limit=1).id})
        found = self.env['pb.division'].sudo().suggest(
            [self.one.id, self.two.id])
        names = {s['name'].lower() for s in found}
        self.assertIn('zq retail', names)
        self.assertIn('zq logistics', names)
        retail = [s for s in found if s['name'].lower() == 'zq retail'][0]
        self.assertEqual(len(retail['departments']), 2,
                         'the same name in two companies is one suggestion')
        self.assertEqual(len({d['company_id']
                              for d in retail['departments']}), 2)

        # A department already in a division is not suggested again.
        division = self.env['pb.division'].sudo().create({'name': 'ZQ Kept'})
        self.env['pb.division.link'].sudo().create({
            'division_id': division.id,
            'department_id': Department.search(
                [('name', '=', 'ZQ Logistics')], limit=1).id})
        again = self.env['pb.division'].sudo().suggest(
            [self.one.id, self.two.id])
        self.assertNotIn('zq logistics',
                         {s['name'].lower() for s in again})

    # ------------------------------------------------------------------ T9
    def test_t9_the_screen_counts_what_the_roster_counts_and_is_quick(self):
        """T9. The facade's headcount against a count written independently."""
        company = self.env.company
        Department = self.env['hr.department'].sudo()
        top = Department.search([('company_id', '=', company.id),
                                 ('parent_id', '=', False)], limit=1)
        if not top:
            top = Department.create({'name': 'ZQ Head', 'company_id': company.id})
        division = self.env['pb.division'].sudo().create({'name': 'ZQ Counted'})
        self.env['pb.division.link'].sudo().create({
            'division_id': division.id, 'department_id': top.id})

        started = time.time()
        room = self.room.get_room()
        took = int((time.time() - started) * 1000)
        self.assertTrue(room['allowed'])
        self.assertLess(took, 500,
                        'the group screen must answer in under half a second')

        row = [d for d in room['divisions'] if d['id'] == division.id][0]

        # The independent count: everybody in that department or under it.
        self.env.cr.execute("""
            WITH open_contract AS (
                SELECT DISTINCT ON (employee_id) employee_id, department_id
                  FROM hr_contract
                 WHERE company_id = %s AND state = 'open'
                 ORDER BY employee_id, wage DESC NULLS LAST, id DESC
            )
            SELECT COUNT(*)
              FROM hr_employee e
         LEFT JOIN hr_version v    ON v.id = e.current_version_id
         LEFT JOIN open_contract c ON c.employee_id = e.id
         LEFT JOIN hr_department d
                ON d.id = COALESCE(c.department_id, v.department_id)
             WHERE e.company_id = %s AND e.active
               AND d.parent_path LIKE %s
        """, (company.id, company.id, '%s/%%' % top.id))
        expected = self.env.cr.fetchone()[0]
        self.assertEqual(row['people'], expected)

    # ----------------------------------------------------------------- T10
    def test_t10_a_reader_may_look_and_may_not_change(self):
        """T10. The refusal is a sentence, not a stack trace."""
        reader = new_test_user(self.env, login='zq_group_reader',
                               groups='base.group_user,hr.group_hr_user')
        room = self.env['pb.group.room'].with_user(reader)
        payload = room.get_room()
        self.assertTrue(payload['allowed'])
        self.assertFalse(payload['can_edit'])
        with self.assertRaises(AccessError):
            room.save_group({'name': 'ZQ Nope',
                             'presentation_currency_id':
                                 self.env.company.currency_id.id,
                             'fx_policy': 'month_end',
                             'fiscal_start_month': 1})

        nobody = new_test_user(self.env, login='zq_group_nobody',
                               groups='base.group_user')
        closed = self.env['pb.group.room'].with_user(nobody).get_room()
        self.assertFalse(closed['allowed'],
                         'a reader with no permission gets an explained empty '
                         'screen and never an access dialog')

    def test_the_screen_writes_what_it_is_asked_to(self):
        """The write path, end to end, the way the screen calls it."""
        payload = self.room.save_group({
            'name': 'ZQ Written group',
            'code': 'ZQW',
            'presentation_currency_id': self.env.company.currency_id.id,
            'fx_policy': 'month_end',
            'fiscal_start_month': 4,
            'company_ids': [self.one.id],
        })
        self.assertTrue(payload['group'])
        group = self.env['pb.group'].sudo().search([('code', '=', 'ZQW')])
        self.assertEqual(group.company_ids.ids, [self.one.id])
        self.assertEqual(group.fiscal_start_month, 4)
        self.assertEqual(group.fiscal_year_start('2026-02-10'),
                         date(2025, 4, 1))

        with self.assertRaises(UserError):
            self.room.save_group({'name': '', 'presentation_currency_id':
                                  self.env.company.currency_id.id,
                                  'fx_policy': 'month_end',
                                  'fiscal_start_month': 1})

    def test_accepting_suggestions_creates_and_attaches(self):
        """The one-button path the divisions board offers."""
        Department = self.env['hr.department'].sudo()
        first = Department.create({'name': 'ZQ Making',
                                   'company_id': self.one.id})
        second = Department.create({'name': 'ZQ Making',
                                    'company_id': self.two.id})
        self.room.accept_suggestions([
            {'name': 'ZQ Making', 'departments': [first.id, second.id]},
        ])
        division = self.env['pb.division'].sudo().search(
            [('name', '=', 'ZQ Making')])
        self.assertEqual(len(division), 1)
        self.assertEqual(len(division.link_ids), 2)

        # Attaching the same department to another division FROM A LATER DAY
        # moves it and keeps the history: the first attachment is closed the
        # day before the second one starts, so last quarter still reads the
        # way it did.
        moved = self.env['pb.division'].sudo().create({'name': 'ZQ Moved to'})
        later = date.today().replace(day=1) + timedelta(days=120)
        self.room.attach_department(moved.id, first.id,
                                    later.strftime('%Y-%m-%d'))
        links = self.env['pb.division.link'].sudo().search(
            [('department_id', '=', first.id)], order='date_from')
        self.assertEqual(len(links), 2)
        self.assertTrue(links[0].date_to)
        self.assertEqual(links[0].date_to, later - timedelta(days=1))
        self.assertEqual(links[1].division_id, moved)

        # And a move BACKWARDS supersedes an attachment that had not started:
        # there is no history to keep, so there is no empty row to explain.
        third = self.env['pb.division'].sudo().create({'name': 'ZQ Third'})
        self.room.attach_department(third.id, second.id,
                                    (date.today()
                                     - timedelta(days=30)).strftime('%Y-%m-%d'))
        second_links = self.env['pb.division.link'].sudo().search(
            [('department_id', '=', second.id)])
        self.assertEqual(len(second_links), 1)
        self.assertEqual(second_links.division_id, third)

    # ----------------------------------------------------------------- T13
    def test_t13_the_demo_modules_company_field_still_works(self):
        """T13. This module deliberately does not define that column."""
        Company = self.env['res.company']
        if 'presentation_currency_id' not in Company._fields:
            self.skipTest('this database has no presentation currency column')
        field = Company._fields['presentation_currency_id']
        self.assertFalse(field.related,
                         'the demo module writes this field directly; making '
                         'it a related read-only column would break it')
        self.one.sudo().presentation_currency_id = self.env.company.currency_id
        self.assertEqual(self.one.sudo().presentation_currency_id,
                         self.env.company.currency_id)
        # And the group still wins over it.
        group = self.env['pb.group'].sudo().create({
            'name': 'ZQ Wins', 'presentation_currency_id': self.env[
                'res.currency'].sudo().search([('name', '=', 'EUR')],
                                              limit=1).id
            or self.env.company.currency_id.id})
        self.one.sudo().pb_group_id = group.id
        self.assertEqual(self.env['pb.fx'].presentation_currency(self.one),
                         group.presentation_currency_id)

    # ----------------------------------------------------------------- T14
    def test_t14_this_module_never_writes_a_branch_parent(self):
        """T14. Ruling G1 as a grep: no assignment to `parent_id` anywhere."""
        offenders = []
        for base, dirs, files in os.walk(HERE):
            dirs[:] = [d for d in dirs
                       if d not in ('__pycache__', 'tests', '.git')]
            for name in files:
                if not name.endswith('.py'):
                    continue
                path = os.path.join(base, name)
                with open(path, encoding='utf-8') as fh:
                    for number, line in enumerate(fh, 1):
                        if re.search(r"""['"]parent_id['"]\s*:""", line):
                            offenders.append('%s:%s' % (name, number))
                        if re.search(r'\.parent_id\s*=', line):
                            offenders.append('%s:%s' % (name, number))
        self.assertFalse(offenders,
                         'the branch tree is never written by this module: %s'
                         % offenders)
