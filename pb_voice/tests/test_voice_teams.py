# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""V-series — follow-up VC1 (owner ruling 2026-11-16 evening): HR sees
results TEAM BY TEAM (the manager card's team groups), on screen and in the
Excel download, with every anonymity guarantee kept:

  * a team under 5 answers shows nothing (no figures, no count, no comments);
  * no subtraction between a team and its department, nor between sibling
    teams and their department, nor across mixed kinds;
  * a team of 1-4 people is never recorded at all, so team x department x day
    cannot point at anybody (no day is stored either).

Second DEMO company "DEMO Two Teams", one department D:
    Anh (no manager), Anh's team: 6 people           -> cell D + team Anh (6)
    Binh (no manager), Binh's team: 6 people         -> cell D + team Binh (6)
    Chi (no manager), Chi's team: 1 person (Rest R1) -> too small, no team
    D rest: 3 people with no manager
    cell "D only": Anh, Binh, Chi, R1, 3 rest        -> 7
"""
import io
import json
import re

import openpyxl

from odoo.tests import new_test_user, tagged

from .common import VoiceCase


@tagged('post_install', '-at_install', 'pb_voice')
class TestVoiceTeams(VoiceCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.co2 = env['res.company'].create({'name': 'DEMO Two Teams'})
        cls.hr.write({'company_ids': [(4, cls.co2.id)]})
        cls.dept_d = env['hr.department'].create({'name': 'DEMO D',
                                                  'company_id': cls.co2.id})

        def person(name, parent=None, dept=True):
            cls._n += 1
            user = new_test_user(env, login='s9c_t%02d' % cls._n, name=name,
                                 company_id=cls.co2.id,
                                 company_ids=[(6, 0, [cls.co2.id])],
                                 groups='base.group_portal')
            emp = env['hr.employee'].create({
                'name': name, 'company_id': cls.co2.id,
                'department_id': cls.dept_d.id if dept else False,
                'parent_id': parent.id if parent else False,
                'user_id': user.id})
            cls.users[emp.id] = user
            return emp

        cls.anh = person('DEMO Anh')
        cls.team_anh = [person('DEMO Anh %d' % i, cls.anh) for i in range(1, 7)]
        cls.binh = person('DEMO Binh')
        cls.team_binh = [person('DEMO Binh %d' % i, cls.binh) for i in range(1, 7)]
        cls.chi = person('DEMO Chi')
        cls.r1 = person('DEMO Lone 1', cls.chi)          # team of ONE
        cls.d_rest = [person('DEMO D rest %d' % i) for i in range(1, 4)]

    def _groups(self, res):
        return {g['name']: g for g in res['groups']}

    def _excel_rows(self, rnd):
        data = self.as_hr(self.Voice).results_xlsx(rnd.id)
        wb = openpyxl.load_workbook(io.BytesIO(data))
        return list(wb['Results'].iter_rows(values_only=True))

    # ------------------------------------------------------------------ V1
    def test_V01_hr_sees_teams_on_screen_and_in_excel(self):
        rnd = self.open_round()
        for emp in self.team_mai:
            self.answer(rnd, emp, scale=5, text='team mai note')
        for emp in self.sales_rest + self.general:
            self.answer(rnd, emp, scale=2)
        self.close(rnd)
        V = self.as_hr(self.Voice)
        res = V.get_results(rnd.id)
        g = self._groups(res)
        team = g["DEMO Mai's team"]
        self.assertTrue(team['shown'])
        self.assertEqual((team['answered'], team['invited']), (7, 7))
        self.assertEqual(team['parent'], 'DEMO Sales')
        tres = V.get_results(rnd.id, group=team['id'])
        fig = tres['figures']
        self.assertEqual(fig['questions'][0]['favourable'], 100)
        self.assertEqual(fig['comments'][0]['items'], ['team mai note'] * 7)
        rows = self._excel_rows(rnd)
        trow = [r for r in rows if r and r[0] == "DEMO Mai's team"]
        self.assertTrue(trow)
        self.assertEqual(trow[0][3], 7)
        # the order on the page: everyone, companies, departments, teams
        kinds = [c['kind'] for c in res['groups']]
        self.assertEqual(kinds, sorted(kinds, key=['all', 'company',
                                                  'department', 'team'].index))

    # ------------------------------------------------------------------ V2
    def test_V02_team_under_five_shows_nothing(self):
        rnd = self.open_round()
        for emp in self.team_mai[:4]:
            self.answer(rnd, emp, scale=1, text='TEAM-SMALL-SECRET')
        for emp in self.sales_rest + self.general:
            self.answer(rnd, emp, scale=4)
        self.close(rnd)
        V = self.as_hr(self.Voice)
        res = V.get_results(rnd.id)
        team = self._groups(res)["DEMO Mai's team"]
        self.assertFalse(team['shown'])
        self.assertIsNone(team['answered'], 'no count either')
        tres = V.get_results(rnd.id, group=team['id'])
        self.assertIsNone(tres['figures'])
        self.assertNotIn('TEAM-SMALL-SECRET', json.dumps(tres))
        trow = [r for r in self._excel_rows(rnd) if r and r[0] == "DEMO Mai's team"]
        self.assertEqual(len(trow), 1)
        self.assertEqual(trow[0][3], 'Hidden')
        self.assertEqual([v for v in trow[0][4:] if v not in (None, '')], [])
        # the manager's own card stays hidden too
        card = self.as_person(self.mai, self.Voice).manager_card(self.mai)
        self.assertNotEqual(card.get('scope'), 'team')

    # ------------------------------------------------------------------ V3
    def test_V03_team_and_its_department_cannot_be_subtracted(self):
        """Mai's team 5, the rest of Sales 2: Sales (7) - team (5) = 2 people."""
        rnd = self.open_round()
        for emp in self.team_mai[:5]:
            self.answer(rnd, emp, scale=5)
        for emp in self.sales_rest[:2]:
            self.answer(rnd, emp, scale=1)
        for emp in self.general:
            self.answer(rnd, emp, scale=3)
        self.close(rnd)
        g = self._groups(self.as_hr(self.Voice).get_results(rnd.id))
        self.assertFalse(g['DEMO Sales']['shown'] and g["DEMO Mai's team"]['shown'])
        shown_rows = [r for r in self._excel_rows(rnd)
                      if r and r[0] in ('DEMO Sales', "DEMO Mai's team")
                      and r[3] != 'Hidden']
        self.assertLessEqual(len({r[0] for r in shown_rows}), 1)
        self._assert_no_small_differences(rnd)

    # ------------------------------------------------------------------ V4
    def test_V04_sibling_teams_and_their_department(self):
        """Anh's team 5 + Binh's team 5 + 3 others in D: D (13) minus both
        shown teams would give the 3 others — one team is hidden."""
        rnd = self.open_round(company=self.co2)
        for emp in self.team_anh[:5]:
            self.answer(rnd, emp, scale=5, text='ANH-NOTE')
        for emp in self.team_binh[:5]:
            self.answer(rnd, emp, scale=1, text='BINH-NOTE')
        for emp in self.d_rest:
            self.answer(rnd, emp, scale=3, text='REST-NOTE')
        self.close(rnd)
        V = self.as_hr(self.Voice)
        res = V.get_results(rnd.id)
        g = self._groups(res)
        self.assertTrue(g['DEMO D']['shown'])
        teams = [g["DEMO Anh's team"], g["DEMO Binh's team"]]
        self.assertEqual(sum(1 for t in teams if t['shown']), 1)
        hidden = [t for t in teams if not t['shown']][0]
        hres = V.get_results(rnd.id, group=hidden['id'])
        self.assertIsNone(hres['figures'])
        shown = [t for t in teams if t['shown']][0]
        sres = json.dumps(V.get_results(rnd.id, group=shown['id'])['figures'])
        self.assertNotIn('REST-NOTE', sres)
        self._assert_no_small_differences(rnd)
        # both teams complete, nobody else: D = the two teams, all shown
        rnd2 = self.open_round(company=self.co2, name='DEMO two teams again')
        for emp in self.team_anh[:5] + self.team_binh[:5]:
            self.answer(rnd2, emp)
        self.close(rnd2)
        g2 = self._groups(V.get_results(rnd2.id))
        self.assertTrue(g2["DEMO Anh's team"]['shown'])
        self.assertTrue(g2["DEMO Binh's team"]['shown'])
        self._assert_no_small_differences(rnd2)

    # ------------------------------------------------------------------ V5
    def test_V05_tiny_teams_are_never_recorded(self):
        """A team of 1 (Chi) and of 4 (Oanh) get no group: nothing ties an
        answer to them through team x department x day."""
        for company in (self.company, self.co2):
            rnd = self.open_round(company=company,
                                  name='DEMO tiny %s' % company.name)
            names = {g.display_name for g in rnd.sudo().group_ids}
            self.assertNotIn("DEMO Chi's team", names)
            self.assertNotIn("DEMO Oanh's team", names)
            invites = rnd.sudo().invite_ids
            per_cell = {}
            for inv in invites:
                per_cell.setdefault(inv.cell, []).append(inv.employee_id)
            for cell, people in per_cell.items():
                self.assertGreaterEqual(len(people), 5, cell)
            team_ids = set(rnd.sudo().group_ids.filtered(
                lambda x: x.kind == 'team').ids)
            for inv in invites:
                if inv.employee_id in (self.r1,) + tuple(self.team_oanh):
                    keys = {int(x) for x in (inv.cell or '').split('.') if x}
                    self.assertFalse(keys & team_ids, inv.employee_id.name)
            # answer as the lone member, then close with enough answers
            if company == self.co2:
                self.answer(rnd, self.r1, scale=1, text='LONE-NOTE')
                for emp in self.team_anh[:5]:
                    self.answer(rnd, emp, scale=5)
                self.close(rnd)
                box = self.Box.sudo().search([('round_id', '=', rnd.id)])
                sealed = json.loads(box.sealed)
                lone_cell = rnd.sudo().invite_ids.filtered(
                    lambda i: i.employee_id == self.r1).cell
                # the lone answer sits in a cell of 7 invited people, with
                # no team and no day
                self.assertEqual(len(per_cell[lone_cell]), 7)
                self.assertIsNone(re.search(r'\d{4}-\d{2}-\d{2}', box.sealed))
                self.assertIn(lone_cell, sealed['cells'])
                self._assert_no_small_differences(rnd)
                g = self._groups(self.as_hr(self.Voice).get_results(rnd.id))
                self.assertNotIn("DEMO Chi's team", g)

    # ------------------------------------------------------------------ V6
    def test_V06_random_patterns_with_teams_never_leak(self):
        import random
        rng = random.Random(23)
        people = ([self.anh, self.binh, self.chi, self.r1] + self.team_anh
                  + self.team_binh + self.d_rest)
        for trial in range(8):
            rnd = self.open_round(company=self.co2, comment=False,
                                  name='DEMO team trial %d' % trial)
            for emp in people:
                if rng.random() < rng.choice((0.4, 0.6, 0.85)):
                    self.answer(rnd, emp, scale=rng.randint(1, 5),
                                enps=rng.randint(0, 10))
            self.close(rnd)
            if rnd.result_state == 'kept':
                self._assert_no_small_differences(rnd)
                res = self.as_hr(self.Voice).get_results(rnd.id)
                for ch in res['groups']:
                    if not ch['shown']:
                        self.assertIsNone(ch['answered'])
