# -*- coding: utf-8 -*-
"""PSCHEME P2a C — "Give everyone their own pay scheme".

T5 plan groups: Ready / From Country of work / Check these / Needs your
   choice (several, none, no country) / Already have their own — one person
   each — and the A13 case (a team line "for any kind of run" is no advance)
T6 apply: rows = plan; source 'fill', from the 1st of this month; a second
   run writes nothing; afterwards every Ready person's answer WITH the person
   rung equals their answer before, for the month and the advance
T7 at size: 5,000 people planned in a bounded number of queries, in time
T8 undo: exactly the fill's untouched rows go; a person changed since keeps
   theirs and is named; the log says so; the answers return to the team
T9 dry mode writes nothing
"""

import logging
import time

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from odoo.addons.pb_scheme_map.models.pb_scheme_map import (
    ADVANCE_RUNGS, MAIN_QUESTION, SKIP_PERSON,
)

from .p2a_common import P2aCase

#: T7 — the plan's ceiling, whatever the head count (measured: well under
#: this at 50 and at 5,000 people; per-person queries would be thousands).
_logger = logging.getLogger(__name__)

QUERY_CEILING = 120
SECONDS_CEILING = 20.0


@tagged('post_install', '-at_install', 'pscheme', 'pscheme_p2a')
class TestP2aFill(P2aCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # the map: Team pays end of month by Vietnam's scheme and gives a REAL
        # advance; Loose has a line "for any kind of run" (no real advance)
        cls.Assign.create({'config_id': cls.vn_end.id, 'cycle_type': 'any',
                           'department_id': cls.team.id, 'company_id': cls.company.id})
        cls.Assign.create({'config_id': cls.vn_mid.id, 'cycle_type': 'mid_cycle',
                           'department_id': cls.team.id, 'company_id': cls.company.id})
        cls.side = cls.env['hr.department'].create({'name': 'DEMO P2A Side',
                                                    'company_id': cls.company.id})
        cls.Assign.create({'config_id': cls.vn_end.id, 'cycle_type': 'any',
                           'department_id': cls.side.id, 'company_id': cls.company.id})
        cls.ready = cls._person('DEMO P2A Ready', cls.team, 'VN')          # + advance
        cls.ready_any = cls._person('DEMO P2A Ready any', cls.side, 'VN')  # A13
        cls.by_country = cls._person('DEMO P2A Country', cls.loose, 'ID')  # ID: one scheme
        cls.check = cls._person('DEMO P2A Check', cls.team, 'SG')          # paid by VN
        cls.several = cls._person('DEMO P2A Several', cls.loose, 'VN')     # VN: two schemes
        cls.none = cls._person('DEMO P2A None', cls.loose, 'MY')           # MY: no scheme
        cls.nocountry = cls._person('DEMO P2A No country', cls.loose, False)
        cls.own = cls._person('DEMO P2A Own', cls.team, 'VN')
        cls.Row.sudo().create({'employee_id': cls.own.id, 'config_id': cls.vn_reg.id,
                               'date_from': cls.first, 'source': 'hand'})

    def plan(self, **kw):
        return self.board().fill_plan(self.company.id, **kw)

    def by_name(self, plan):
        return {r['name']: r for r in plan['rows']}

    # ==================================================================== T5
    def test_t5_plan_groups(self):
        plan = self.plan()
        rows = self.by_name(plan)
        self.assertEqual(rows['DEMO P2A Ready']['group'], 'ready')
        self.assertEqual(rows['DEMO P2A Ready']['target_id'], self.vn_end.id)
        self.assertEqual(rows['DEMO P2A Ready']['advance_id'], self.vn_mid.id)
        # A13: a team line "for any kind of run" answers the advance question
        # with the main scheme — never copied as an advance
        self.assertEqual(rows['DEMO P2A Ready any']['group'], 'ready')
        self.assertEqual(rows['DEMO P2A Ready any']['advance_id'], 0)
        self.assertEqual(rows['DEMO P2A Country']['group'], 'country')
        self.assertEqual(rows['DEMO P2A Country']['target_id'], self.id_end.id)
        check = rows['DEMO P2A Check']
        self.assertEqual((check['group'], check['target_id'], check['reason']),
                         ('check', 0, 'other_country'))
        self.assertEqual(check['options'][0], self.vn_end.id)        # keep today's
        self.assertIn(self.sg_end.id, check['options'])
        self.assertEqual(check['country_pick'], self.sg_end.id)
        several = rows['DEMO P2A Several']
        self.assertEqual((several['group'], several['reason']), ('choice', 'several'))
        self.assertEqual(set(several['options']), {self.vn_end.id, self.vn_reg.id})
        none = rows['DEMO P2A None']
        self.assertEqual((none['group'], none['reason'], none['fix']),
                         ('choice', 'no_scheme', 'mapping'))
        nocountry = rows['DEMO P2A No country']
        self.assertEqual((nocountry['group'], nocountry['reason'], nocountry['fix']),
                         ('choice', 'no_country', 'cow'))
        self.assertNotIn('DEMO P2A Own', rows)
        self.assertEqual(plan['counts'], {'ready': 2, 'country': 1, 'check': 1,
                                          'choice': 3, 'own': 1})
        self.assertEqual(plan['people'], 8)
        self.assertEqual(plan['date'], str(self.first))
        self.assertIsNone(plan['latest'])

    # ==================================================================== T6
    def test_t6_apply_rows_equal_the_plan(self):
        ready = self.ready | self.ready_any
        cycle = self.env['hr.employee']._pb_main_cycle(self.company.id)

        def answers(people):
            main = self.Map.with_context(**{MAIN_QUESTION: True}).resolve_many(people.ids, cycle)
            mid = self.Map.resolve_many(people.ids, 'mid_cycle')
            return {e: (main[e]['config_id'],
                        mid[e]['config_id'] if mid[e]['rung'] in ADVANCE_RUNGS
                        and self.env['hr.formula.config'].browse(mid[e]['config_id']).cycle_type
                        == 'mid_cycle' else 0) for e in people.ids}
        before = answers(ready)
        out = self.board().fill_apply(self.company.id, picks={
            str(self.several.id): self.vn_reg.id})
        self.assertTrue(out['applied'], out)
        self.assertEqual(out['people'], 4)          # 2 ready + 1 country + 1 pick
        self.assertEqual(self.rows_of(self.ready), sorted([
            (self.vn_end, self.first, False, 'fill'), (self.vn_mid, self.first, False, 'fill')],
            key=lambda r: r[0].cycle_type == 'mid_cycle'))
        self.assertEqual(self.rows_of(self.ready_any), [(self.vn_end, self.first, False, 'fill')])
        self.assertEqual(self.rows_of(self.by_country), [(self.id_end, self.first, False, 'fill')])
        self.assertEqual(self.rows_of(self.several), [(self.vn_reg, self.first, False, 'fill')])
        for person in (self.check, self.none, self.nocountry):
            self.assertFalse(self.rows_of(person), person.name)
        self.assertEqual(len(self.rows_of(self.own)), 1)
        # with the person rung, the Ready people answer exactly as before
        self.assertEqual(answers(ready), before)
        self.assertTrue(all(a['rung'] == 'person' for a in self.Map.resolve_many(
            ready.ids, 'end_cycle').values()))
        fill = self.Fill.search([('company_id', '=', self.company.id)])
        self.assertEqual(len(fill), 1)
        self.assertEqual(fill.people_count, 4)
        self.assertEqual(fill.row_count, 5)
        # a second run writes nothing: everybody filled is "Already have their own"
        rows = self.Row.sudo().search_count([])
        plan = self.plan()
        self.assertEqual(plan['counts']['own'], 5)
        self.assertEqual(plan['counts']['ready'] + plan['counts']['country'], 0)
        with self.assertRaisesRegex(UserError, 'Nobody is ticked'):
            self.board().fill_apply(self.company.id)
        self.assertEqual(self.Row.sudo().search_count([]), rows)
        self.assertEqual(self.Fill.search_count([('company_id', '=', self.company.id)]), 1)

    # ==================================================================== T7
    def test_t7_five_thousand_people(self):
        """5,000 people cloned in SQL from one employee (a create through the
        ORM costs minutes); they share that employee's team and record."""
        big = self.env['hr.department'].create({'name': 'DEMO P2A Big',
                                                'company_id': self.company.id})
        seed = self._person('DEMO P2A Seed', big, 'VN')
        self.env.flush_all()
        cr = self.env.cr
        cr.execute("""SELECT column_name FROM information_schema.columns
                       WHERE table_name = 'hr_employee' AND column_name NOT IN ('id', 'name')""")
        cols = [r[0] for r in cr.fetchall()]
        listed = ', '.join('"%s"' % c for c in cols)
        cr.execute("""
            INSERT INTO hr_employee (name, %s)
            SELECT 'DEMO P2A Big ' || g, %s FROM hr_employee, generate_series(1, 4999) g
             WHERE id = %%s""" % (listed, listed), (seed.id,))
        self.env.invalidate_all()
        Board = self.board()
        Board.fill_plan(self.company.id)                    # warm the caches once
        counts = {}
        for label in ('small', 'big'):
            ids = (self.ready | self.check | self.several).ids if label == 'small' else None
            start_q, start = cr.sql_log_count, time.time()
            plan = Board.fill_plan(self.company.id, employee_ids=ids)
            counts[label] = (cr.sql_log_count - start_q, time.time() - start, plan)
        queries, seconds, plan = counts['big']
        _logger.info('T7 plan: %s people, %s queries, %.2f s (3 people: %s queries)',
                     plan['people'], queries, seconds, counts['small'][0])
        self.assertGreaterEqual(plan['people'], 5000)
        self.assertEqual(plan['counts']['country'] + plan['counts']['ready'] + plan['counts']['choice']
                         + plan['counts']['check'] + plan['counts']['own'], plan['people'])
        self.assertLessEqual(queries, QUERY_CEILING, counts)
        self.assertLess(seconds, SECONDS_CEILING, counts)
        # bounded: 5,000 people cost (almost) no more queries than three
        self.assertLessEqual(queries - counts['small'][0], 15, counts)

    # ==================================================================== T8
    def test_t8_undo(self):
        Board = self.board()
        Board.fill_apply(self.company.id)
        fill = self.Fill.search([('company_id', '=', self.company.id)])
        self.assertEqual(fill.state, 'done')
        # somebody changes "Country" since: they keep everything of theirs
        Board.person_set(self.by_country.ids, self.vn_end.id, False, str(self.next_first))
        latest = Board.fill_plan(self.company.id)['latest']
        self.assertEqual(latest['undo']['kept'], ['DEMO P2A Country'])
        self.assertEqual(latest['undo']['people'], 2)
        out = Board.fill_undo(fill.id, self.company.id)
        self.assertTrue(out['applied'], out)
        self.assertEqual(out['kept'], 1)
        self.assertEqual(out['removed'], 3)                  # ready (2 rows) + ready any
        self.assertFalse(self.rows_of(self.ready))
        self.assertFalse(self.rows_of(self.ready_any))
        self.assertTrue(self.rows_of(self.by_country))
        self.assertEqual(len(self.rows_of(self.own)), 1)     # never the fill's
        self.assertEqual(fill.state, 'undone')
        self.assertIn('DEMO P2A Country', fill.kept_json)
        # back to the team
        answer = self.Map.resolve_many(self.ready.ids, 'end_cycle')[self.ready.id]
        self.assertEqual((answer['rung'], answer['config_id']), ('department', self.vn_end.id))
        self.assertEqual(self.Map.resolve_many(self.ready.ids, 'mid_cycle')[self.ready.id]['config_id'],
                         self.vn_mid.id)
        with self.assertRaisesRegex(UserError, 'already undone'):
            Board.fill_undo(fill.id, self.company.id)
        # the plan shows the undone fill, and offers the fill again
        plan = Board.fill_plan(self.company.id)
        self.assertEqual(plan['latest']['state'], 'undone')
        self.assertEqual(plan['counts']['ready'], 2)

    # ==================================================================== T9
    def test_t9_dry_writes_nothing(self):
        def counts():
            return (self.Row.sudo().search_count([]), self.Fill.sudo().search_count([]),
                    self.env['pb.schememap.proposal'].sudo().search_count([]),
                    self.env['hr.formula.scheme.assignment'].sudo().search_count([]))
        before = counts()
        out = self.board().fill_apply(self.company.id, ['ready', 'country'], dry=True)
        self.assertTrue(out['dry'])
        self.assertEqual(out['people'], 3)
        self.assertEqual(out['by_group'], {'ready': 2, 'country': 1})
        self.assertEqual(out['left'], 4)
        self.assertEqual(sum(s['people'] for s in out['schemes']), 3)
        self.assertEqual(counts(), before)
        # the plan itself writes nothing either, and skips the person rung
        self.board().fill_plan(self.company.id)
        self.assertEqual(counts(), before)
        self.assertTrue(SKIP_PERSON)
