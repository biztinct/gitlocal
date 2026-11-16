# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""R-series: results by group, the floor of 5 (numbers AND comments), no
working anything out by subtraction, the Excel download, the manager card."""
import io
import json

import openpyxl

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from .common import VoiceCase


@tagged('post_install', '-at_install', 'pb_voice')
class TestVoiceResults(VoiceCase):

    def _groups(self, res):
        return {g['name']: g for g in res['groups']}

    def _gid(self, rnd, kind, name):
        for g in rnd.sudo().group_ids:
            if g.kind == kind and g.display_name == name:
                return g.id
        return None

    # ------------------------------------------------------------------ R1
    def test_R01_results_only_after_close(self):
        rnd = self.open_round()
        for emp in self.team_mai[:6]:
            self.answer(rnd, emp)
        res = self.as_hr(self.Voice).get_results(rnd.id)
        self.assertEqual(res['state'], 'not_closed')
        self.assertNotIn('figures', res)
        self.assertNotIn('groups', res)

    # ------------------------------------------------------------------ R2
    def test_R02_small_group_hidden_numbers_and_comments(self):
        rnd = self.open_round()
        # Sales 6 (Mai's team), Ops 3, General 5
        for emp in self.team_mai[:6]:
            self.answer(rnd, emp, scale=5, text='sales says hi')
        for emp in self.team_oanh[:3]:
            self.answer(rnd, emp, scale=1, text='OPS-SECRET')
        for emp in self.general:
            self.answer(rnd, emp, scale=3, text='general view')
        self.close(rnd)
        Voice = self.as_hr(self.Voice)
        res = Voice.get_results(rnd.id)
        g = self._groups(res)
        self.assertTrue(g['DEMO Sales']['shown'])
        self.assertFalse(g['DEMO Ops']['shown'])
        self.assertIsNone(g['DEMO Ops']['answered'], 'no count for a hidden group')
        ops = Voice.get_results(rnd.id, group=g['DEMO Ops']['id'])
        self.assertIsNone(ops['figures'])
        self.assertNotIn('OPS-SECRET', json.dumps(ops))
        sales = Voice.get_results(rnd.id, group=g['DEMO Sales']['id'])
        dumped = json.dumps(sales['figures'])
        self.assertIn('sales says hi', dumped)
        self.assertNotIn('OPS-SECRET', dumped)
        self.assertNotIn('general view', dumped)
        # the whole round (14 answers) shows everything, comments included
        overall = Voice.get_results(rnd.id)
        self.assertIn('OPS-SECRET', json.dumps(overall['figures']))
        self.assertEqual(overall['group']['answered'], 14)
        # VC1: teams are offered on HR's page too; Mai's team (6) is shown
        team = g["DEMO Mai's team"]
        self.assertEqual(team['kind'], 'team')
        self.assertEqual(team['parent'], 'DEMO Sales')
        self.assertTrue(team['shown'])
        tres = Voice.get_results(rnd.id, group=team['id'])
        self.assertEqual(tres['group']['answered'], 6)
        self.assertIn('sales says hi', json.dumps(tres['figures']))
        self.assertNotIn('OPS-SECRET', json.dumps(tres['figures']))

    # ------------------------------------------------------------------ R3
    def test_R03_pair_rule_no_subtraction_between_company_and_part(self):
        """Company 8 answers, Sales 6 shown would give the other 2 by
        subtraction: Sales is hidden too."""
        rnd = self.open_round()
        for emp in self.team_mai[:6]:
            self.answer(rnd, emp, scale=5)
        for emp in self.general[:2]:
            self.answer(rnd, emp, scale=1)
        self.close(rnd)
        res = self.as_hr(self.Voice).get_results(rnd.id)
        g = self._groups(res)
        self.assertTrue(g['Everyone asked']['shown'])
        self.assertFalse(g['DEMO Sales']['shown'])
        self.assertFalse(g['DEMO Voice Co']['shown'] and g['DEMO Sales']['shown'])
        # and the manager's team (same 6 people) is hidden as well
        groups, cells_of, resp, visible = self.Voice._plan(
            rnd, self.Voice._sealed(rnd))
        team = self._gid(rnd, 'team', "DEMO Mai's team")
        self.assertNotIn(team, visible)

    # ------------------------------------------------------------------ R4
    def test_R04_parts_rule_company_minus_shown_departments(self):
        """Sales 5, Ops 5, General 3: company minus the two shown departments
        would give General's 3 — one department is hidden too."""
        rnd = self.open_round()
        for emp in self.sales_rest:
            self.answer(rnd, emp, scale=5)
        for emp in self.ops_rest + self.team_oanh[:3]:
            self.answer(rnd, emp, scale=2)
        for emp in self.general[:3]:
            self.answer(rnd, emp, scale=1)
        self.close(rnd)
        res = self.as_hr(self.Voice).get_results(rnd.id)
        g = self._groups(res)
        self.assertEqual(g['Everyone asked']['answered'], 13)
        shown_depts = [n for n in ('DEMO Sales', 'DEMO Ops') if g[n]['shown']]
        self.assertEqual(len(shown_depts), 1, 'one department hidden')
        # whatever is shown, no visible group differs from another by 1-4
        self._assert_no_small_differences(rnd)

    # ------------------------------------------------------------------ R5
    def test_R05_team_and_department_cannot_be_subtracted(self):
        """Mai's team 5, the rest of Sales 2: Sales (7) minus the team (5)
        would give 2 people's answers — one of them is hidden."""
        rnd = self.open_round()
        for emp in self.team_mai[:5]:
            self.answer(rnd, emp, scale=5)
        for emp in self.sales_rest[:2]:
            self.answer(rnd, emp, scale=1)
        for emp in self.general:
            self.answer(rnd, emp, scale=3)
        self.close(rnd)
        groups, cells_of, resp, visible = self.Voice._plan(
            rnd, self.Voice._sealed(rnd))
        team = self._gid(rnd, 'team', "DEMO Mai's team")
        sales = self._gid(rnd, 'department', 'DEMO Sales')
        self.assertFalse(team in visible and sales in visible)
        self._assert_no_small_differences(rnd)

    def test_R05b_many_random_patterns_never_leak(self):
        """Many answer patterns: the plan never leaves a small difference."""
        import random
        rng = random.Random(9)
        for trial in range(6):
            rnd = self.open_round(comment=False, name='DEMO trial %d' % trial)
            for emp in self.everyone:
                if rng.random() < rng.choice((0.3, 0.5, 0.8)):
                    self.answer(rnd, emp, scale=rng.randint(1, 5),
                                enps=rng.randint(0, 10))
            self.close(rnd)
            if rnd.result_state == 'kept':
                self._assert_no_small_differences(rnd)

    # ------------------------------------------------------------------ R6
    def test_R06_figures(self):
        rnd = self.open_round(choice=True)
        values = [(5, 10, 0), (4, 9, 0), (4, 8, 1), (2, 3, 1), (1, 0, 1), (5, 10, 1)]
        for emp, (s, e, c) in zip(self.team_mai[:6], values):
            self.answer(rnd, emp, scale=s, enps=e, choice=c)
        self.close(rnd)
        fig = self.as_hr(self.Voice).get_results(rnd.id)['figures']
        qs = {q['kind']: q for q in fig['questions']}
        self.assertEqual(qs['scale']['favourable'], 67)    # 4 of 6
        self.assertEqual(qs['scale']['avg'], 3.5)
        self.assertEqual(qs['enps']['promoters'], 50)      # 3 of 6
        self.assertEqual(qs['enps']['detractors'], 33)     # 2 of 6
        self.assertEqual(qs['enps']['score'], 17)
        self.assertEqual([d['n'] for d in qs['choice']['dist']], [2, 4])
        self.assertEqual(fig['themes'][0]['label'], 'Your manager')
        self.assertEqual(fig['rate'], 22)                  # 6 of 27

    # ------------------------------------------------------------------ R7
    def test_R07_excel_same_rules(self):
        rnd = self.open_round()
        for emp in self.team_mai[:6]:
            self.answer(rnd, emp, scale=5, text='excel comment')
        for emp in self.team_oanh[:3]:
            self.answer(rnd, emp, scale=1)
        for emp in self.general:
            self.answer(rnd, emp, scale=3)
        self.close(rnd)
        data = self.as_hr(self.Voice).results_xlsx(rnd.id)
        wb = openpyxl.load_workbook(io.BytesIO(data))
        rows = list(wb['Results'].iter_rows(values_only=True))
        ops_rows = [r for r in rows if r and r[0] == 'DEMO Ops']
        self.assertEqual(len(ops_rows), 1)
        self.assertEqual(ops_rows[0][3], 'Hidden')
        self.assertEqual([v for v in ops_rows[0][4:] if v not in (None, '')], [])
        self.assertTrue([r for r in rows if r and r[0] == 'DEMO Sales'
                         and r[3] == 6])
        comments = [r[1] for r in wb['Comments'].iter_rows(values_only=True)]
        self.assertIn('excel comment', comments)
        for r in rows:
            for v in r or ():
                self.assertNotIn('Odoo', str(v or ''))

    def test_R07b_excel_route_refuses_non_hr(self):
        rnd = self.open_round()
        for emp in self.team_mai[:5]:
            self.answer(rnd, emp)
        self.close(rnd)
        portal = self.users[self.team_mai[0].id]
        with self.assertRaises(AccessError):
            self.Voice.with_user(portal).with_context(
                allowed_company_ids=[self.company.id]).results_xlsx(rnd.id)

    # ------------------------------------------------------------------ R8
    def test_R08_manager_card_own_team_when_five_or_more(self):
        rnd = self.open_round()
        for emp in self.team_mai:
            self.answer(rnd, emp, scale=4, text='TEAM-COMMENT')
        for emp in self.sales_rest:
            self.answer(rnd, emp, scale=2)
        for emp in self.team_oanh + self.ops_rest:
            self.answer(rnd, emp, scale=3)
        self.close(rnd)
        card = self.as_person(self.mai, self.Voice).manager_card(self.mai)
        self.assertTrue(card['shown'])
        self.assertEqual(card['scope'], 'team')
        self.assertEqual(card['answered'], 7)
        self.assertNotIn('TEAM-COMMENT', json.dumps(card, default=str))
        self.assertNotIn('comments', card)
        # Oanh's team is 4 people: her card shows her department instead
        card_o = self.as_person(self.oanh, self.Voice).manager_card(self.oanh)
        self.assertTrue(card_o['shown'])
        self.assertEqual(card_o['scope'], 'department')
        self.assertEqual(card_o['label'], 'DEMO Ops')
        # nobody reads another manager's card
        self.assertIsNone(self.as_person(self.oanh, self.Voice).manager_card(self.mai))

    def test_R08b_manager_card_hidden_when_too_few(self):
        rnd = self.open_round()
        for emp in self.team_mai[:4]:
            self.answer(rnd, emp)
        for emp in self.general:
            self.answer(rnd, emp)
        self.close(rnd)
        card = self.as_person(self.mai, self.Voice).manager_card(self.mai)
        self.assertFalse(card['shown'])
        self.assertNotIn('themes', card)
        self.assertNotIn('enps', card)
        self.assertIn('5 or more', card['sentence'])

    def test_R08c_no_card_before_any_round(self):
        self.assertIsNone(self.as_person(self.mai, self.Voice).manager_card(self.mai))

    # ------------------------------------------------------------------ R9
    def test_R09_hr_of_another_company_sees_nothing(self):
        rnd = self.open_round()
        for emp in self.team_mai[:5]:
            self.answer(rnd, emp)
        self.close(rnd)
        other = self.env['res.company'].create({'name': 'DEMO Other Voice Co'})
        hr2 = new_test_user(self.env, login='s9c_hr2', company_id=other.id,
                            company_ids=[(6, 0, [other.id])],
                            groups='base.group_user,hr.group_hr_user')
        V = self.Voice.with_user(hr2).with_context(allowed_company_ids=[other.id])
        with self.assertRaises(Exception):
            V.get_results(rnd.id)
        self.assertEqual(V.get_board()['rounds'], [])
        # a plain staff login is refused the board
        plain = new_test_user(self.env, login='s9c_plain', company_id=self.company.id,
                              groups='base.group_user')
        self.assertFalse(self.Voice.with_user(plain).get_board()['allowed'])
        with self.assertRaises(AccessError):
            self.Voice.with_user(plain).get_results(rnd.id)
